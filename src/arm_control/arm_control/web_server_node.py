#!/usr/bin/env python3
import io, os, secrets, sys, threading, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from arm_interfaces.msg import ArmCmd, ArmStatus
from std_msgs.msg import String, Float64MultiArray, Int32MultiArray, Int32
import database as db
import auth_rbac as auth
from arm_interfaces.srv import GripperCmd
import asyncio
import threading
import rclpy
from flask import request, jsonify
from flask_socketio import emit
try:
    from flask import Flask, jsonify, redirect, request, send_from_directory, send_file, session
    from flask_socketio import SocketIO, emit
    _FLASK = True
except ImportError:
    _FLASK = False

QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=10)
from ament_index_python.packages import get_package_share_directory
WEB_DIR = Path(get_package_share_directory('arm_control')) / 'web'
AVATARS_DIR = Path.home() / 'arm_ws' / 'system' / 'uploads' / 'profiles'
START_TS    = time.time()

# Homing config (اختياري – موجود مسبقاً)
HOMING_CONFIG = {
    'M4': {
        'motor_id': 4,
        'direction': -1,
        'ls_index': 5,
        'ls_name': 'LS6',
        'speed': 1200,
        'accel': 5000,
    },
    'M1': {
        'motor_id': 1,
        'direction': +1,
        'ls_index': 6,
        'ls_name': 'LS7',
        'speed': 1200,
        'accel': 5000,
    },
}

_homing_active = False


def uptime_str():
    s = int(time.time() - START_TS); h,m = divmod(s//60,60)
    return f'{h:02d}h {m:02d}m {s%60:02d}s'

class WebServerNode(Node):
    def __init__(self):
        super().__init__('web_server_node')
        self.declare_parameter('http_port', 8080)
        self._port = self.get_parameter('http_port').value
        self._arm  = {'positions':[0.0]*6,'moving':[False]*6,'raw':'','ts':0.0}
        self._lock = threading.Lock()
        self._uart=False; self._ros2=False; self._last=0.0

        self._enc_counts = [0.0]*6
        self._limit_states = [0]*8
        self._gripper_state = "UNKNOWN"
        self._gripper_count = 0
        self._lock_sensors = threading.Lock()

        # ─── Publishers ───────────────────────────────────────────
        self._pub  = self.create_publisher(ArmCmd, '/arm/cmd', QOS)
        # ⭐ إضافة ناشر لإعادة تعيين المشفرات
        self._enc_reset_pub = self.create_publisher(Int32, '/arm/encoder/reset', QOS)

        # ─── Gripper service client ───────────────────────────────
        self._gripper_cli = self.create_client(GripperCmd, '/arm/gripper/cmd')
        while not self._gripper_cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /arm/gripper/cmd service...')
        self.get_logger().info('Gripper service client ready')

        # ─── Subscriptions ────────────────────────────────────────
        self.create_subscription(ArmStatus,'/arm/status',self._on_status,QOS)
        self.create_subscription(String,'/arm/raw_rx',self._on_raw,QOS)
        self.create_subscription(Float64MultiArray, '/arm/encoder/counts', self._on_enc_counts, QOS)
        self.create_subscription(Int32MultiArray, '/arm/limit/states', self._on_limit_states, QOS)
        self.create_subscription(String, '/arm/gripper/state', self._on_gripper_state, QOS)
        self.create_subscription(Int32, '/arm/gripper/count', self._on_gripper_count, QOS)

        self.create_timer(1.0, self._watchdog)
        if _FLASK: self._start_flask()
        self.get_logger().info(f'Web: http://0.0.0.0:{self._port}')

    # ─── Status callbacks ────────────────────────────────────────
    def _on_status(self,msg):
        self._last=time.time(); self._uart=self._ros2=True
        with self._lock:
            self._arm.update({'positions':list(msg.positions),'moving':list(msg.moving),'raw':msg.raw_response,'ts':time.time()})
        if hasattr(self,'_sio'): self._sio.emit('arm_status',self._snap())

    def _on_raw(self,msg):
        with self._lock: self._arm['raw']=msg.data

    # ─── Sensor callbacks ────────────────────────────────────────
    def _on_enc_counts(self, msg):
        with self._lock_sensors:
            self._enc_counts = list(msg.data[:6])
        self._emit_sensors()

    def _on_limit_states(self, msg):
        with self._lock_sensors:
            self._limit_states = list(msg.data[:8])
        self._emit_sensors()

    def _on_gripper_state(self, msg):
        with self._lock_sensors:
            self._gripper_state = msg.data
        self._emit_sensors()

    def _on_gripper_count(self, msg):
        with self._lock_sensors:
            self._gripper_count = msg.data
        self._emit_sensors()

    def _emit_sensors(self):
        if hasattr(self, '_sio'):
            try:
                self._sio.emit('sensors_update', self._get_sensors_snapshot())
            except Exception as e:
                self.get_logger().warn(f'emit sensors error: {e}')

    def _get_sensors_snapshot(self):
        with self._lock_sensors:
            return {
                'encoders': list(self._enc_counts),
                'limits':   list(self._limit_states),
                'gripper': {
                    'state': self._gripper_state,
                    'count': self._gripper_count,
                }
            }

    def _watchdog(self):
        a=time.time()-self._last; self._ros2=a<3.0; self._uart=a<5.0

    def _snap(self):
        with self._lock: return dict(self._arm)

    def _send_arm(self, data):
        msg=ArmCmd(); msg.command=str(data.get('command','STATUS')).upper()
        msg.motor_id=int(data.get('motor_id',0)); msg.angle=float(data.get('angle',0.0))
        msg.speed=float(data.get('speed',0.0)); msg.accel=float(data.get('accel',0.0))
        self._pub.publish(msg)

    # ⭐ دالة مساعدة لإعادة تعيين مشفر (أو الكل)
    def _reset_encoder(self, channel):
        """
        channel: 0 -> reset all, 1..6 -> reset single encoder
        """
        msg = Int32()
        msg.data = channel
        self._enc_reset_pub.publish(msg)
        self.get_logger().info(f'[RESET] Published reset for channel {channel}')

    # ─── Homing helpers (موجودة سابقاً) ──────────────────────────
    def _send_arm_direct(self, motor_id, angle, speed, accel):
        self._send_arm({'command':'MOVE','motor_id':motor_id,'angle':angle,'speed':speed,'accel':accel})

    def _send_stop(self, motor_id):
        self._send_arm({'command':'STOP','motor_id':motor_id,'angle':0,'speed':0,'accel':0})

    def _send_zero(self, motor_id):
        self._send_arm({'command':'ZERO','motor_id':motor_id,'angle':0,'speed':0,'accel':0})

    def _get_limit_switches(self):
        with self._lock_sensors:
            return list(self._limit_states)

    # ═══════════════════════════════════════════════════════════════
    #  FLASK + SOCKET.IO (الإصدار المعدل)
    # ═══════════════════════════════════════════════════════════════
    def _start_flask(self):
        app = Flask(__name__)
        app.secret_key = secrets.token_hex(32)
        app.config['MAX_CONTENT_LENGTH'] = 3*1024*1024

        sio = SocketIO(
            app,
            cors_allowed_origins='*',
            async_mode='threading',
            allow_upgrades=False,       # منع مشاكل WebSocket
            logger=False,
            engineio_logger=False,
        )
        self._sio = sio

        me  = auth.get_current_user
        ok  = lambda d=None: jsonify({'ok':True,**(d or {})})
        err = lambda m,c=400: (jsonify({'ok':False,'message':m}),c)
        ip  = lambda: request.headers.get('X-Forwarded-For',request.remote_addr) or ''

        # ── PAGES (كما هي) ─────────────────────────────────────────
        @app.route('/login')
        def r_login():
            return redirect('/') if me() else send_from_directory(WEB_DIR,'login.html')

        @app.route('/denied')
        def r_denied(): return send_from_directory(WEB_DIR,'denied.html')

        @app.route('/')
        def r_ctrl():
            u=me()
            if not u: return redirect('/login')
            if not db.user_can(u['user_id'],'control',u['role']): return redirect('/denied')
            return send_from_directory(WEB_DIR,'control.html')

        @app.route('/monitor')
        def r_mon():
            u=me()
            if not u: return redirect('/login')
            if not db.user_can(u['user_id'],'monitor',u['role']): return redirect('/denied')
            return send_from_directory(WEB_DIR,'monitor.html')

        @app.route('/admin')
        def r_adm():
            u=me()
            if not u: return redirect('/login')
            if u['role']!='admin': return redirect('/denied')
            return send_from_directory(WEB_DIR,'admin.html')

        @app.route('/account')
        def r_acc():
            u=me()
            if not u: return redirect('/login')
            return send_from_directory(WEB_DIR,'account.html')

        @app.route('/logs')
        def r_logs():
            u=me()
            if not u: return redirect('/login')
            if u['role']!='admin': return redirect('/denied')
            return send_from_directory(WEB_DIR,'logs.html')

        @app.route('/programmer')
        @app.route('/robot_programmer.html')
        @auth.require_login
        def r_programmer():
            u = me()
            if not db.user_can(u['user_id'], 'control', u['role']): return redirect('/denied')
            return send_from_directory(WEB_DIR, 'robot_programmer.html')

        @app.route('/sensor.html')
        @app.route('/Sensor.html')
        @auth.require_login
        def r_sensor():
            return send_from_directory(WEB_DIR, 'sensor.html')

        @app.route('/<path:f>')
        def r_assets(f):
            if f.endswith('.html'): return redirect('/login')
            return send_from_directory(WEB_DIR, f)

        # ── HEALTH ─────────────────────────────────────────────────
        @app.route('/api/health')
        def r_health():
            return ok({'host':os.uname().nodename,'uart':self._uart,'ros':self._ros2,'uptime':uptime_str()})

        # ── AUTH (نفس الكود الأصلي) ────────────────────────────────
        @app.route('/api/auth/login', methods=['POST'])
        def r_auth_login():
            cip=ip(); locked,rem=auth.is_ip_locked(cip)
            if locked: return err(f'Locked — wait {rem}s',429)
            d=request.get_json(force=True,silent=True) or {}
            un=str(d.get('username','')).strip(); pw=str(d.get('password',''))
            user=db.get_user_by_username(un)
            if user and user['status']=='active' and auth.verify_password(pw,user['password_hash']):
                auth.clear_fails(cip); auth.login_user(user['id'])
                db.update_last_login(user['id'],cip)
                db.log_action(user['id'],un,'LOGIN','Success',cip)
                return ok({'username':un,'role':user['role'],'permissions':db.get_user_permissions(user['id'])})
            r2,lk=auth.record_fail(cip)
            msg=('Account inactive' if user and user['status']!='active'
                 else f'Invalid credentials — {r2} left' if not lk else f'Locked {auth.LOCKOUT_SEC}s')
            db.log_action(None,un,'LOGIN_FAIL',msg,cip)
            return err(msg,401)

        @app.route('/api/auth/logout', methods=['POST'])
        def r_auth_logout():
            u=me()
            if u: db.log_action(u['user_id'],u['username'],'LOGOUT','',ip())
            auth.logout_user(); return ok()

        @app.route('/api/auth/logout-all', methods=['POST'])
        def r_auth_logout_all():
            u=me()
            if u: db.delete_all_user_sessions(u['user_id']); db.log_action(u['user_id'],u['username'],'LOGOUT_ALL','',ip())
            session.clear(); return ok()

        # ── ME ─────────────────────────────────────────────────────
        @app.route('/api/me')
        @auth.require_login
        def r_me():
            u=me(); user=db.get_user_by_id(u['user_id'])
            return ok({'id':user['id'],'username':user['username'],'display_name':user['display_name'],
                'email':user['email'],'role':user['role'],'status':user['status'],
                'avatar_url':f'/api/me/avatar?t={int(time.time())}' if user['avatar'] else None,
                'permissions':db.get_user_permissions(u['user_id']),
                'last_login':user['last_login'],'last_ip':user['last_ip'],
                'created_at':user['created_at'],'uptime':uptime_str()})

        @app.route('/api/me', methods=['PATCH'])
        @auth.require_login
        def r_me_patch():
            u=me(); d=request.get_json(force=True,silent=True) or {}
            db.update_user_profile(u['user_id'],display_name=d.get('display_name'),email=d.get('email'))
            db.log_action(u['user_id'],u['username'],'PROFILE_UPDATE','',ip()); return ok()

        @app.route('/api/me/password', methods=['POST'])
        @auth.require_login
        def r_me_pw():
            u=me(); user=db.get_user_by_id(u['user_id'])
            d=request.get_json(force=True,silent=True) or {}
            if not auth.verify_password(str(d.get('current_password','')),user['password_hash']):
                return err('Current password incorrect',401)
            nw=str(d.get('new_password',''))
            if len(nw)<8: return err('Min 8 characters',400)
            db.update_user_password(u['user_id'],auth.hash_password(nw))
            db.log_action(u['user_id'],u['username'],'PASSWORD_CHANGE','',ip()); return ok()

        @app.route('/api/me/avatar', methods=['POST'])
        @auth.require_login
        def r_me_avatar_post():
            u=me(); f=request.files.get('avatar')
            if not f: return err('No file',400)
            if f.mimetype not in {'image/jpeg','image/png','image/webp'}: return err('Unsupported format',400)
            fn=f'user_{u["user_id"]}.jpg'; path=AVATARS_DIR/fn; AVATARS_DIR.mkdir(parents=True,exist_ok=True)
            try:
                try:
                    from PIL import Image; img=Image.open(f.stream).convert('RGB'); img.thumbnail((256,256)); img.save(str(path),'JPEG',quality=85)
                except ImportError:
                    f.stream.seek(0); path.write_bytes(f.stream.read())
                db.update_user_profile(u['user_id'],avatar=fn)
                db.log_action(u['user_id'],u['username'],'AVATAR_UPDATE','',ip())
                return ok({'avatar_url':f'/api/me/avatar?t={int(time.time())}'})
            except Exception as e: return err(f'Upload failed: {e}',500)

        @app.route('/api/me/avatar')
        @auth.require_login
        def r_me_avatar_get():
            u=me(); user=db.get_user_by_id(u['user_id'])
            if not user['avatar']: return err('No avatar',404)
            path=AVATARS_DIR/user['avatar']
            return send_file(str(path),mimetype='image/jpeg') if path.exists() else err('Not found',404)

        @app.route('/api/me/sessions')
        @auth.require_login
        def r_me_sessions():
            u=me(); rows=db.get_user_sessions(u['user_id']); return ok({'sessions':[dict(r) for r in rows]})

        @app.route('/api/me/sessions/<int:sid>', methods=['DELETE'])
        @auth.require_login
        def r_me_sess_del(sid):
            u=me(); db.delete_session_by_id(sid,u['user_id']); return ok()

        # ── ADMIN ──────────────────────────────────────────────────
        @app.route('/api/admin/users')
        @auth.require_role('admin')
        def r_adm_users():
            rows=db.get_all_users()
            out=[{**dict(r),'avatar_url':f'/api/admin/avatar/{r["id"]}' if r['avatar'] else None,
                  'permissions':db.get_user_permissions(r['id'])} for r in rows]
            return ok({'users':out})

        @app.route('/api/admin/users', methods=['POST'])
        @auth.require_role('admin')
        def r_adm_create():
            u=me(); d=request.get_json(force=True,silent=True) or {}
            un=str(d.get('username','')).strip(); pw=str(d.get('password',''))
            role=str(d.get('role','viewer'))
            if not un or not pw: return err('Username and password required',400)
            if len(pw)<8: return err('Password min 8 chars',400)
            if role not in ('admin','operator','viewer'): return err('Invalid role',400)
            if db.get_user_by_username(un): return err('Username taken',409)
            uid=db.create_user(un,auth.hash_password(pw),role,str(d.get('display_name','')),str(d.get('email','')))
            db.log_action(u['user_id'],u['username'],'USER_CREATE',f'{un} role={role}',ip())
            return ok({'id':uid})

        @app.route('/api/admin/users/<int:uid>', methods=['PATCH'])
        @auth.require_role('admin')
        def r_adm_upd(uid):
            u=me()
            if uid==u['user_id']: return err('Cannot modify own account here',400)
            d=request.get_json(force=True,silent=True) or {}
            db.admin_update_user(uid,d)
            if 'new_password' in d and len(str(d['new_password']))>=8:
                db.update_user_password(uid,auth.hash_password(str(d['new_password'])))
            db.log_action(u['user_id'],u['username'],'USER_UPDATE',f'uid={uid}',ip()); return ok()

        @app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
        @auth.require_role('admin')
        def r_adm_del(uid):
            u=me()
            if uid==u['user_id']: return err('Cannot delete own account',400)
            user=db.get_user_by_id(uid); db.delete_all_user_sessions(uid); db.delete_user(uid)
            db.log_action(u['user_id'],u['username'],'USER_DELETE',user['username'] if user else str(uid),ip()); return ok()

        @app.route('/api/admin/users/<int:uid>/permissions', methods=['PUT'])
        @auth.require_role('admin')
        def r_adm_perms(uid):
            u=me(); d=request.get_json(force=True,silent=True) or {}
            pages=[str(p) for p in d.get('pages',[])]
            db.set_all_permissions(uid,pages,u['role'])
            db.log_action(u['user_id'],u['username'],'PERMISSION_SET',f'uid={uid} pages={pages}',ip()); return ok()

        @app.route('/api/admin/avatar/<int:uid>')
        @auth.require_role('admin')
        def r_adm_avatar(uid):
            user=db.get_user_by_id(uid)
            if not user or not user['avatar']: return err('No avatar',404)
            path=AVATARS_DIR/user['avatar']
            return send_file(str(path),mimetype='image/jpeg') if path.exists() else err('Not found',404)

        @app.route('/api/admin/logs')
        @auth.require_role('admin')
        def r_adm_logs():
            un=request.args.get('username'); action=request.args.get('action')
            limit=min(int(request.args.get('limit',200)),500)
            rows=db.get_logs(limit,un,action); return ok({'logs':[dict(r) for r in rows]})

        # ── ARM ────────────────────────────────────────────────────
        @app.route('/api/arm/status')
        def r_arm_status():
            u=me()
            if not db.user_can(u['user_id'],'monitor',u['role']): return err('Access denied',403)
            return jsonify(self._snap())

        @app.route('/api/arm/cmd', methods=['POST'])
        @auth.require_login
        def r_arm_cmd():
            u = me()
            if not db.user_can(u['user_id'], 'control', u['role']):
                return err('Access denied', 403)
            try:
                data = request.get_json(force=True, silent=True)
                if data is None:
                    return err('Invalid JSON body', 400)
                self._send_arm(data)
                return ok()
            except Exception as e:
                app.logger.error(f"Error in /api/arm/cmd: {e}")
                return err('Internal server error', 500)

        # ════════════════════════════════════════════════════════════
        # ⭐ ENCODER RESET API (REST) — تستخدمه صفحة sensor.html
        # ════════════════════════════════════════════════════════════
        @app.route('/api/encoder/reset', methods=['POST'])
        @auth.require_login
        def api_encoder_reset():
            u = me()
            if not db.user_can(u['user_id'], 'control', u['role']):
                return err('Access denied', 403)
            data = request.get_json(force=True, silent=True) or {}
            all_flag = data.get('all', False)
            encoders = data.get('encoders', [])
            if all_flag or encoders == 'all':
                self._reset_encoder(0)   # channel 0 = reset all
                self.get_logger().info('[API] Reset all encoders')
                return jsonify({'ok': True, 'message': 'Reset all encoders'})
            if not isinstance(encoders, list) or not encoders:
                return err('Invalid encoder list', 400)
            for ch in encoders:
                try:
                    ch_num = int(ch)
                    if 1 <= ch_num <= 6:
                        self._reset_encoder(ch_num)
                    else:
                        self.get_logger().warn(f'[API] Invalid encoder ID {ch_num}')
                except:
                    pass
            self.get_logger().info(f'[API] Reset encoders: {encoders}')
            return jsonify({'ok': True, 'message': f'Reset encoders {encoders}'})

        # ── SENSORS API ────────────────────────────────────────────
        @app.route('/api/sensors/gripper')
        @auth.require_login
        def r_gripper():
            u = me()
            if not db.user_can(u['user_id'], 'monitor', u['role']): return err('Access denied', 403)
            return ok(self._get_sensors_snapshot()['gripper'])

        @app.route('/api/sensors/encoders')
        @auth.require_login
        def r_encoders():
            u = me()
            if not db.user_can(u['user_id'], 'monitor', u['role']): return err('Access denied', 403)
            return ok({'counts': self._get_sensors_snapshot()['encoders']})

        @app.route('/api/sensors/limits')
        @auth.require_login
        def r_limits():
            u = me()
            if not db.user_can(u['user_id'], 'monitor', u['role']): return err('Access denied', 403)
            return ok({'states': self._get_sensors_snapshot()['limits']})

        @app.route('/api/sensors/all')
        @auth.require_login
        def r_sensors_all():
            u = me()
            if not db.user_can(u['user_id'], 'monitor', u['role']): return err('Access denied', 403)
            return ok(self._get_sensors_snapshot())

        # ── ARM HOME ───────────────────────────────────────────────
        @app.route('/api/arm/home', methods=['POST'])
        @auth.require_login
        def r_arm_home():
            u = me()
            if not db.user_can(u['user_id'], 'control', u['role']): return err('Access denied', 403)
            global _homing_active
            if _homing_active:
                return jsonify({'success': False, 'msg': 'Homing already in progress'}), 409
            _homing_active = True
            threading.Thread(target=self._run_homing_sequence, daemon=True).start()
            return jsonify({'success': True, 'msg': 'Homing started — M4(LS6) then M1(LS7)'})

        # ── PROGRAMS API ───────────────────────────────────────────
        @app.route('/api/programs', methods=['GET'])
        @auth.require_login
        def r_programs_list():
            rows = db.get_all_programs()
            import json
            out = [{'id':r['id'],'name':r['name'],'username':r['username'],
                    'created_by':r['created_by'],'created_at':r['created_at'],'updated_at':r['updated_at']}
                   for r in rows]
            return ok({'programs': out})

        @app.route('/api/programs', methods=['POST'])
        @auth.require_login
        def r_programs_save():
            import json
            u = me()
            d = request.get_json(force=True, silent=True) or {}
            name = str(d.get('name', '')).strip()
            blocks = d.get('blocks', [])
            if not name: return err('Program name required', 400)
            pid = d.get('id')
            blocks_json = json.dumps(blocks)
            if pid:
                ok2 = db.update_program(int(pid), name, blocks_json, u['user_id'])
                if not ok2:
                    pid = db.save_program(name, blocks_json, u['user_id'], u['username'])
                else:
                    db.log_action(u['user_id'], u['username'], 'PROGRAM_UPDATE', name, ip())
                    return ok({'id': int(pid)})
            else:
                pid = db.save_program(name, blocks_json, u['user_id'], u['username'])
            db.log_action(u['user_id'], u['username'], 'PROGRAM_SAVE', name, ip())
            return ok({'id': pid})

        @app.route('/api/programs/<int:pid>', methods=['GET'])
        @auth.require_login
        def r_programs_get(pid):
            import json
            row = db.get_program(pid)
            if not row: return err('Not found', 404)
            return ok({'id':row['id'],'name':row['name'],'blocks':json.loads(row['blocks']),
                       'username':row['username'],'created_at':row['created_at'],'updated_at':row['updated_at']})

        @app.route('/api/programs/<int:pid>', methods=['DELETE'])
        @auth.require_login
        def r_programs_delete(pid):
            u = me()
            ok2 = db.delete_program(pid, u['user_id'], u['role'])
            if not ok2: return err('Not found or access denied', 403)
            db.log_action(u['user_id'], u['username'], 'PROGRAM_DELETE', str(pid), ip())
            return ok()

        # ── SOCKET.IO EVENTS ───────────────────────────────────────
        @sio.on('arm_cmd')
        def on_arm_cmd(data):
            self._send_arm(data)
            emit('ack', {'ok': True})

        @sio.on('gripper_cmd')
        def on_gripper_cmd(data):
            cmd = data.get('command')
            if not cmd:
                emit('gripper_ack', {'ok': False, 'message': 'Missing command'})
                return
            self.get_logger().info(f'Gripper command via WS: {cmd}')
            req = GripperCmd.Request()
            req.command = cmd
            try:
                resp = self._gripper_cli.call(req, timeout_sec=3.0)
                emit('gripper_ack', {'ok': resp.success, 'message': resp.message})
            except Exception as e:
                self.get_logger().error(f'Gripper service call failed: {e}')
                emit('gripper_ack', {'ok': False, 'message': str(e)})

        @sio.on('arm_home')
        def on_arm_home(data):
            global _homing_active
            if _homing_active:
                emit('home_error', {'msg': 'Homing already in progress'})
                return
            _homing_active = True
            threading.Thread(target=self._run_homing_sequence, daemon=True).start()

        # ⭐⭐ ENCODER RESET VIA SOCKET.IO (للواجهات التي تستخدم WebSockets)
        @sio.on('encoder_reset')
        def on_encoder_reset(data):
            u = auth.get_current_user()
            if not u or not db.user_can(u['user_id'], 'control', u['role']):
                emit('encoder_reset_ack', {'success': False, 'msg': 'Access denied'})
                return
            all_flag = data.get('all', False)
            encoders = data.get('encoders', [])
            self.get_logger().info(f'[SOCKET] Encoder reset request: {data}')
            if all_flag or encoders == 'all':
                self._reset_encoder(0)
                emit('encoder_reset_ack', {'success': True, 'encoders': 'all', 'all': True})
                return
            if isinstance(encoders, list):
                for ch in encoders:
                    try:
                        ch_num = int(ch)
                        if 1 <= ch_num <= 6:
                            self._reset_encoder(ch_num)
                    except:
                        pass
                emit('encoder_reset_ack', {'success': True, 'encoders': encoders, 'all': False})
            else:
                emit('encoder_reset_ack', {'success': False, 'msg': 'Invalid encoder list'})

        # ── PUSH THREAD (بث دوري للحالة) ───────────────────────────
        def push():
            while True:
                time.sleep(0.1)
                try:
                    sio.emit('arm_status', self._snap())
                except Exception:
                    pass

        threading.Thread(target=push, daemon=True).start()

        # ── START FLASK SERVER ─────────────────────────────────────
        threading.Thread(
            target=lambda: sio.run(
                app,
                host='0.0.0.0',
                port=self._port,
                debug=False,
                allow_unsafe_werkzeug=True,
            ),
            daemon=True,
        ).start()

    # ═══════════════════════════════════════════════════════════════
    #  HOMING SEQUENCE (كما هو موجود مسبقاً)
    # ═══════════════════════════════════════════════════════════════
    def _run_homing_sequence(self):
        global _homing_active

        def progress(step, msg):
            try: self._sio.emit('home_progress', {'step': step, 'msg': msg})
            except Exception: pass

        def home_error(msg):
            global _homing_active
            try: self._sio.emit('home_error', {'msg': msg})
            except Exception: pass
            _homing_active = False

        try:
            POLL    = 0.02
            TIMEOUT = 30.0

            # ─── M4 ───
            cfg4 = HOMING_CONFIG['M4']
            progress('m4_moving', f"M4 → NEGATIVE {cfg4['speed']} steps/s … waiting {cfg4['ls_name']}")
            self._send_arm_direct(cfg4['motor_id'], -9999, cfg4['speed'], cfg4['accel'])

            elapsed = 0.0
            triggered = False
            while elapsed < TIMEOUT:
                ls = self._get_limit_switches()
                if len(ls) > cfg4['ls_index'] and ls[cfg4['ls_index']]:
                    triggered = True
                    break
                threading.Event().wait(POLL)
                elapsed += POLL

            if not triggered:
                self._send_stop(cfg4['motor_id'])
                home_error(f"TIMEOUT: {cfg4['ls_name']} not triggered — M4 stopped")
                return

            self._send_stop(cfg4['motor_id'])
            threading.Event().wait(0.15)

            progress('m4_zero', f"{cfg4['ls_name']} ✓ — Zeroing M4")
            self._send_zero(cfg4['motor_id'])
            threading.Event().wait(0.15)

            # ─── M1 ───
            cfg1 = HOMING_CONFIG['M1']
            progress('m1_moving', f"M1 → POSITIVE {cfg1['speed']} steps/s … waiting {cfg1['ls_name']}")
            self._send_arm_direct(cfg1['motor_id'], +9999, cfg1['speed'], cfg1['accel'])

            elapsed = 0.0
            triggered = False
            while elapsed < TIMEOUT:
                ls = self._get_limit_switches()
                if len(ls) > cfg1['ls_index'] and ls[cfg1['ls_index']]:
                    triggered = True
                    break
                threading.Event().wait(POLL)
                elapsed += POLL

            if not triggered:
                self._send_stop(cfg1['motor_id'])
                home_error(f"TIMEOUT: {cfg1['ls_name']} not triggered — M1 stopped")
                return

            self._send_stop(cfg1['motor_id'])
            threading.Event().wait(0.15)

            progress('m1_zero', f"{cfg1['ls_name']} ✓ — Zeroing M1")
            self._send_zero(cfg1['motor_id'])
            threading.Event().wait(0.15)

            try: self._sio.emit('home_complete', {})
            except Exception: pass

        except Exception as ex:
            home_error(f"Homing exception: {ex}")
        finally:
            _homing_active = False


def main(args=None):
    rclpy.init(args=args)
    node = WebServerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()