#!/usr/bin/env bash
# ARM Robot Dashboard - Fixed version (no set -e, graceful fallback)

DASH_LOG="$HOME/.arm_dashboard.log"
exec 2>>"$DASH_LOG"

TW=$(tput cols 2>/dev/null || echo 80)
TH=$(tput lines 2>/dev/null || echo 24)
[ "$TW" -lt 40 ] && TW=80
[ "$TH" -lt 20 ] && TH=24

# Colors
RST='\033[0m'; BOLD='\033[1m'; DIM='\033[2m'
RED='\033[31m'; GRN='\033[32m'; YEL='\033[33m'; CYN='\033[36m'
BRED='\033[91m'; BGRN='\033[92m'; BYEL='\033[93m'; BCYN='\033[96m'; BWHT='\033[97m'

# Paths
ARM_WS="$HOME/arm_ws"
LOG_DIR="$HOME/.ros/log"
WEB_URL="http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):8080"

# Helper: run command safely
safe_cmd() {
    cmd="$1"
    eval "$cmd" 2>/dev/null || echo ""
}

center() {
    local text="$1"
    local clean=$(echo -e "$text" | sed 's/\x1B\[[0-9;]*m//g')
    local len=${#clean}
    local pad=$(( (TW - len) / 2 ))
    [ $pad -lt 0 ] && pad=0
    printf "%${pad}s" ""
    echo -e "$text"
}

draw_header() {
    echo ""
    center "${BCYN}${BOLD}╔════════════════════════════════════════════════════════╗${RST}"
    center "${BCYN}${BOLD}║${RST}   ${BWHT}${BOLD} ▄▄▄  ██████  ███    ███ ${RST}   ${BYEL}${BOLD}ROBOT ARM CONTROL${RST}    ${BCYN}${BOLD}║${RST}"
    center "${BCYN}${BOLD}║${RST}   ${BWHT}${BOLD}▀▀██  ██   ██ ████  ████ ${RST}   ${DIM}ROS2 · STM32 · Flask${RST} ${BCYN}${BOLD}║${RST}"
    center "${BCYN}${BOLD}║${RST}   ${BWHT}${BOLD}  ██  ██████  ██ ████ ██ ${RST}   ${BCYN}v1.2 · Jazzy${RST}        ${BCYN}${BOLD}║${RST}"
    center "${BCYN}${BOLD}║${RST}   ${BWHT}${BOLD}  ██  ██   ██ ██  ██  ██ ${RST}   ${DIM}$(date '+%Y-%m-%d  %H:%M:%S')${RST}   ${BCYN}${BOLD}║${RST}"
    center "${BCYN}${BOLD}╚════════════════════════════════════════════════════════╝${RST}"
    echo ""
}

get_cpu_temp() {
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        t=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
        echo "$((t/1000))°C"
    else
        echo "N/A"
    fi
}

get_cpu_usage() {
    # Simple fallback using top if /proc/stat fails
    if [ -r /proc/stat ]; then
        read -r cpu < /proc/stat
        cpu=${cpu#cpu }
        set -- $cpu
        idle1=$4; total1=$(( $1+$2+$3+$4+$5+$6+$7+$8 ))
        sleep 0.2
        read -r cpu < /proc/stat
        cpu=${cpu#cpu }
        set -- $cpu
        idle2=$4; total2=$(( $1+$2+$3+$4+$5+$6+$7+$8 ))
        diff_total=$(( total2 - total1 ))
        diff_idle=$(( idle2 - idle1 ))
        if [ $diff_total -gt 0 ]; then
            usage=$(( 100 * (diff_total - diff_idle) / diff_total ))
            echo "${usage:-0}"
            return
        fi
    fi
    # fallback
    top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 || echo "?"
}

get_mem_usage() {
    free -m 2>/dev/null | awk '/Mem:/ { if ($2>0) printf "%.0f%%", $3/$2*100; else print "0%" }' || echo "0%"
}

get_disk_usage() {
    df -h / 2>/dev/null | awk 'NR==2 {print $5}' || echo "0%"
}

get_uptime() {
    uptime -p 2>/dev/null | sed 's/up //' || uptime | awk '{print $3,$4}' | tr -d ','
}

get_ip() {
    hostname -I 2>/dev/null | awk '{print $1}' || echo "No IP"
}

get_uart_status() {
    if [ -e /dev/ttyAMA2 ]; then echo "OK"; else echo "ERR"; fi
}

is_node_running() {
    # Ignore errors from ros2 command
    ros2 node list 2>/dev/null | grep -q "$1" 2>/dev/null
    return $?
}

dot_status() {
    if [ "$1" = "true" ] || [ "$1" = "OK" ]; then
        echo -e "${BGRN}●${RST}"
    else
        echo -e "${BRED}●${RST}"
    fi
}

draw_status() {
    local cpu_temp=$(get_cpu_temp)
    local cpu_use=$(get_cpu_usage)
    local mem_use=$(get_mem_usage)
    local disk_use=$(get_disk_usage)
    local uptime_val=$(get_uptime)
    local ip=$(get_ip)
    local uart=$(get_uart_status)

    local web_ok="false"; enc_ok="false"; uart_ok="false"
    is_node_running "web_server_node" && web_ok="true"
    is_node_running "stm32_encoder_node" && enc_ok="true"
    is_node_running "uart_node" && uart_ok="true"

    local temp_color="$BGRN"
    local temp_num=${cpu_temp//[^0-9]/}
    [ "$temp_num" -gt 70 ] 2>/dev/null && temp_color="$BYEL"
    [ "$temp_num" -gt 80 ] 2>/dev/null && temp_color="$BRED"

    echo -e "${DIM}┌─ SYSTEM ──────────────────────────────┬─ ROS2 NODES ─────────────────────────┐${RST}"
    printf "${DIM}│${RST} ${CYN}%-8s${RST} ${BWHT}%-12s${RST}  ${CYN}%-8s${RST} ${BWHT}%-10s${RST}  ${DIM}│${RST} " "IP" "$ip" "UPTIME" "$uptime_val"
    printf "$(dot_status $web_ok) ${BWHT}%-20s${RST} ${DIM}│${RST}\n" "web_server_node"

    printf "${DIM}│${RST} ${CYN}%-8s${RST} ${temp_color}%-12s${RST}  ${CYN}%-8s${RST} ${BWHT}%-10s${RST}  ${DIM}│${RST} " "CPU TEMP" "$cpu_temp" "CPU USE" "${cpu_use}%"
    printf "$(dot_status $enc_ok) ${BWHT}%-20s${RST} ${DIM}│${RST}\n" "stm32_encoder_node"

    printf "${DIM}│${RST} ${CYN}%-8s${RST} ${BWHT}%-12s${RST}  ${CYN}%-8s${RST} ${BWHT}%-10s${RST}  ${DIM}│${RST} " "MEMORY" "$mem_use" "DISK" "$disk_use"
    printf "$(dot_status $uart_ok) ${BWHT}%-20s${RST} ${DIM}│${RST}\n" "uart_node"

    printf "${DIM}│${RST} ${CYN}%-8s${RST} " "UART"
    if [ "$uart" = "OK" ]; then
        printf "${BGRN}%-12s${RST}" "/dev/ttyAMA2 ✓"
    else
        printf "${BRED}%-12s${RST}" "NOT FOUND ✗"
    fi
    printf "  ${CYN}%-8s${RST} ${BWHT}%-10s${RST}  ${DIM}│${RST} " "WEB" "$WEB_URL"
    printf "${DIM}%-28s│${RST}\n" ""
    echo -e "${DIM}└───────────────────────────────────────┴────────────────────────────────────┘${RST}"
    echo ""
}

draw_menu() {
    echo -e "${DIM}┌─ ACTIONS ─────────────────────────────────────────────────────────────────────┐${RST}"
    echo ""
    printf "  ${BCYN}[1]${RST} ${BWHT}%-22s${RST}  │  ${BCYN}[5]${RST} ${BWHT}%-22s${RST}\n" "🚀  Launch System" "📊  Live Topics"
    printf "  ${BCYN}[2]${RST} ${BWHT}%-22s${RST}  │  ${BCYN}[6]${RST} ${BWHT}%-22s${RST}\n" "🔴  Stop System" "🌐  Open Web UI (curl)"
    printf "  ${BCYN}[3]${RST} ${BWHT}%-22s${RST}  │  ${BCYN}[7]${RST} ${BWHT}%-22s${RST}\n" "🔨  Build Package" "🖥️  Open Browser (GUI)"
    printf "  ${BCYN}[4]${RST} ${BWHT}%-22s${RST}  │  ${BCYN}[8]${RST} ${BWHT}%-22s${RST}\n" "📋  View Logs" "🔌  Test UART Sensors"
    echo ""
    printf "  ${BCYN}[9]${RST} ${BWHT}%-22s${RST}  │  ${BCYN}[W]${RST} ${BWHT}%-22s${RST}\n" "💾  Source ROS2" "🔄  Watch Mode"
    printf "  ${BCYN}[R]${RST} ${BWHT}%-22s${RST}  │  ${BCYN}[0]${RST} ${BRED}%-22s${RST}\n" "♻️  Restart System" "❌  Exit Dashboard"
    echo ""
    echo -e "${DIM}└───────────────────────────────────────────────────────────────────────────────┘${RST}"
    echo ""
    echo -ne "  ${DIM}Press a key:${RST} ${BCYN}${BOLD}"
}

action_launch() { echo -e "\n${BCYN}Launching...${RST}"; cd "$ARM_WS" && source install/setup.bash && ros2 launch arm_control arm.launch.py; read -r; }
action_stop() { echo -e "\n${BRED}Stopping...${RST}"; pkill -f "ros2 launch" 2>/dev/null; pkill -f "stm32_encoder_node\|web_server_node\|uart_node"; sleep 1; }
action_build() { echo -e "\n${BYEL}Building...${RST}"; cd "$ARM_WS" && colcon build --packages-select arm_control; read -r; }
action_logs() { echo -e "\n${BCYN}Logs...${RST}"; latest=$(ls -td "$LOG_DIR"/2* 2>/dev/null | head -1); if [ -n "$latest" ]; then tail -40 "$latest"/*/streams.log 2>/dev/null; else echo "No logs"; fi; read -r; }
action_topics() { echo -e "\n${BCYN}Topics...${RST}"; source /opt/ros/jazzy/setup.bash 2>/dev/null; source "$ARM_WS/install/setup.bash" 2>/dev/null; ros2 topic list; read -r; }
action_web_curl() { curl -s "http://$(get_ip):8080/api/health" | python3 -m json.tool 2>/dev/null || echo "Web not reachable"; read -r; }
action_browser() { xdg-open "http://$(get_ip):8080" 2>/dev/null || echo "No browser"; read -r; }
action_uart_test() { ls -la /dev/ttyAMA*; read -r; }
action_restart() { action_stop; sleep 1; action_launch; }
action_source() { echo -e "\n${BYEL}source /opt/ros/jazzy/setup.bash\nsource $ARM_WS/install/setup.bash${RST}"; read -r; }
action_watch() { while true; do clear; draw_header; draw_status; draw_menu; sleep 2; done; }

draw_dashboard() { clear; draw_header; draw_status; draw_menu; }

# Initial source (optional, ignore errors)
source /opt/ros/jazzy/setup.bash 2>/dev/null || true
source "$ARM_WS/install/setup.bash" 2>/dev/null || true

while true; do
    draw_dashboard
    read -rsn1 choice
    echo -e "${RST}"
    case "$choice" in
        1) action_launch ;;
        2) action_stop ;;
        3) action_build ;;
        4) action_logs ;;
        5) action_topics ;;
        6) action_web_curl ;;
        7) action_browser ;;
        8) action_uart_test ;;
        9) action_source ;;
        r|R) action_restart ;;
        w|W) action_watch ;;
        0|q|Q) clear; center "${BCYN}Goodbye!${RST}"; exit 0 ;;
    esac
done