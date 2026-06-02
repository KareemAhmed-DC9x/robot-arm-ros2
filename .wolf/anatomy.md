# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-05-19T00:14:41.555Z
> Files: 508 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `arm_dashboard.sh` — ARM Robot Dashboard - Fixed version (no set -e, graceful fallback) (~2478 tok)
- `arm.launch.py` — generate_launch_description (~599 tok)
- `CLAUDE.md` — OpenWolf (~57 tok)
- `codefinalSensor.py` — C: parse_lines (~7404 tok)
- `operator_profile.json` (~22 tok)
- `py2.py` — debug (~244 tok)
- `robot_arm.log` (~5166 tok)
- `stm32_encoder.py` — C: parse_lines (~5030 tok)
- `users.json` (~125 tok)

## .claude/

- `settings.json` (~441 tok)

## .claude/rules/

- `openwolf.md` (~313 tok)

## install/

- `_local_setup_util_ps1.py` — URL configuration (~4245 tok)
- `_local_setup_util_sh.py` — URL configuration (~4293 tok)
- `.colcon_install_layout` (~3 tok)
- `COLCON_IGNORE` (~0 tok)
- `local_setup.bash` — This script extends the environment with all packages contained in this (~1003 tok)
- `local_setup.ps1` — This script extends the environment with all packages contained in this (~546 tok)
- `local_setup.sh` — This script extends the environment with all packages contained in this (~1237 tok)
- `local_setup.zsh` — This script extends the environment with all packages contained in this (~1108 tok)
- `setup.bash` — This script extends the environment with the environment of other prefix (~304 tok)
- `setup.ps1` — This script extends the environment with the environment of other prefix (~311 tok)
- `setup.sh` — This script extends the environment with the environment of other prefix (~544 tok)
- `setup.zsh` — This script extends the environment with the environment of other prefix (~301 tok)

## install/arm_control/lib/arm_control/

- `stm32_encoder_node` — EASY-INSTALL-ENTRY-SCRIPT: 'arm-control==1.0.0','console_scripts','stm32_encoder_node' (~265 tok)
- `uart_node` — EASY-INSTALL-ENTRY-SCRIPT: 'arm-control==1.0.0','console_scripts','uart_node' (~260 tok)
- `web_server_node` — EASY-INSTALL-ENTRY-SCRIPT: 'arm-control==1.0.0','console_scripts','web_server_node' (~263 tok)

## install/arm_control/lib/python3.12/site-packages/arm_control-1.0.0-py3.12.egg-info/

- `dependency_links.txt` (~1 tok)
- `entry_points.txt` (~42 tok)
- `PKG-INFO` (~45 tok)
- `requires.txt` (~3 tok)
- `SOURCES.txt` (~253 tok)
- `top_level.txt` (~3 tok)
- `zip-safe` (~1 tok)

## install/arm_control/lib/python3.12/site-packages/arm_control/

- `__init__.py` (~0 tok)
- `auth_rbac.py` — hash_password, verify_password, login_user, logout_user + 12 more (~1569 tok)
- `database.py` — get_db, init_db, create_user, get_user_by_id + 16 more (~4215 tok)
- `stm32_encoder_node.py` — STM32EncoderNode: subscriber (~3479 tok)
- `stm32_encoder.py` — C: parse_lines, get_limit, get_all_limits, get_encoder_level + 9 more (~3856 tok)
- `uart_node.py` — UartNode: main (~2138 tok)
- `web_server_node.py` — API router (~6496 tok)

## install/arm_control/share/ament_index/resource_index/packages/

- `arm_control` (~0 tok)

## install/arm_control/share/arm_control/

- `package.bash` — This script extends the environment for this package. (~287 tok)
- `package.dsv` (~78 tok)
- `package.ps1` — function to append a value to a variable (~868 tok)
- `package.sh` — This script extends the environment for this package. (~817 tok)
- `package.xml` (~172 tok)
- `package.zsh` — This script extends the environment for this package. (~363 tok)

## install/arm_control/share/arm_control/hook/

- `ament_prefix_path.dsv` (~11 tok)
- `ament_prefix_path.ps1` (~41 tok)
- `ament_prefix_path.sh` (~41 tok)
- `pythonpath.dsv` (~17 tok)
- `pythonpath.ps1` (~47 tok)
- `pythonpath.sh` (~47 tok)

## install/arm_control/share/arm_control/launch/

- `arm.launch.py` — generate_launch_description (~750 tok)

## install/arm_control/share/arm_control/web/

- `auth_guard.js` — auth_guard.js (~558 tok)
- `login.html` — ARM CONTROL | Secure Access (~5959 tok)
- `logs.html` — ARM | System Logs (~6335 tok)
- `nav.js` — Declares ALL_LINKS (~4368 tok)
- `robot_programmer.html` — ARM Programmer (~12185 tok)

## install/arm_control/share/colcon-core/packages/

- `arm_control` (~8 tok)

## install/arm_interfaces/share/arm_interfaces/

- `package.bash` — This script extends the environment for this package. (~368 tok)
- `package.dsv` (~186 tok)
- `package.ps1` — function to append a value to a variable (~930 tok)
- `package.sh` — This script extends the environment for this package. (~877 tok)
- `package.zsh` — This script extends the environment for this package. (~444 tok)

## install/arm_interfaces/share/arm_interfaces/cmake/

- `arm_interfaces__rosidl_typesupport_cExport-noconfig.cmake` — Commands may need to know the format version. (~323 tok)
- `arm_interfaces__rosidl_typesupport_cExport.cmake` (~1388 tok)
- `arm_interfaces__rosidl_typesupport_cppExport-noconfig.cmake` — Commands may need to know the format version. (~340 tok)
- `arm_interfaces__rosidl_typesupport_cppExport.cmake` (~1422 tok)
- `arm_interfaces__rosidl_typesupport_introspection_cExport-noconfig.cmake` — Commands may need to know the format version. (~319 tok)
- `arm_interfaces__rosidl_typesupport_introspection_cExport.cmake` (~1482 tok)
- `arm_interfaces__rosidl_typesupport_introspection_cppExport-noconfig.cmake` — Commands may need to know the format version. (~324 tok)
- `arm_interfaces__rosidl_typesupport_introspection_cppExport.cmake` (~1516 tok)
- `export_arm_interfaces__rosidl_generator_cExport-noconfig.cmake` — Commands may need to know the format version. (~285 tok)
- `export_arm_interfaces__rosidl_generator_cExport.cmake` (~1203 tok)
- `export_arm_interfaces__rosidl_generator_cppExport.cmake` (~1199 tok)
- `export_arm_interfaces__rosidl_generator_pyExport-noconfig.cmake` — Commands may need to know the format version. (~693 tok)
- `export_arm_interfaces__rosidl_generator_pyExport.cmake` (~1049 tok)
- `export_arm_interfaces__rosidl_typesupport_fastrtps_cExport-noconfig.cmake` — Commands may need to know the format version. (~309 tok)
- `export_arm_interfaces__rosidl_typesupport_fastrtps_cExport.cmake` (~1501 tok)
- `export_arm_interfaces__rosidl_typesupport_fastrtps_cppExport-noconfig.cmake` — Commands may need to know the format version. (~313 tok)
- `export_arm_interfaces__rosidl_typesupport_fastrtps_cppExport.cmake` (~1520 tok)

## install/arm_interfaces/share/arm_interfaces/hook/

- `cmake_prefix_path.dsv` (~11 tok)
- `cmake_prefix_path.ps1` (~41 tok)
- `cmake_prefix_path.sh` (~41 tok)
- `ld_library_path_lib.dsv` (~12 tok)
- `ld_library_path_lib.ps1` (~42 tok)
- `ld_library_path_lib.sh` (~42 tok)
- `pythonpath.dsv` (~17 tok)
- `pythonpath.ps1` (~47 tok)
- `pythonpath.sh` (~47 tok)

## install/arm_interfaces/share/colcon-core/packages/

- `arm_interfaces` (~8 tok)

## log/

- `COLCON_IGNORE` (~0 tok)

## log/build_2026-05-06_04-01-29/

- `events.log` (~6392 tok)
- `logger_all.log` (~7116 tok)

## log/build_2026-05-06_04-01-29/arm_control/

- `command.log` (~343 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~315 tok)
- `stdout.log` (~315 tok)
- `streams.log` (~711 tok)

## log/build_2026-05-06_04-01-29/arm_interfaces/

- `command.log` (~314 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` — The C compiler identification is GNU 13.3.0 (~843 tok)
- `stdout.log` — The C compiler identification is GNU 13.3.0 (~843 tok)
- `streams.log` (~1274 tok)

## log/build_2026-05-06_04-08-11/

- `events.log` — Declares hashes (~14879 tok)
- `logger_all.log` (~7744 tok)

## log/build_2026-05-06_04-08-11/arm_control/

- `command.log` (~349 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~152 tok)
- `stdout.log` (~152 tok)
- `streams.log` (~537 tok)

## log/build_2026-05-06_04-08-11/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` — Found ament_cmake: 2.5.6 (/opt/ros/jazzy/share/ament_cmake/cmake) (~6725 tok)
- `stdout.log` — Found ament_cmake: 2.5.6 (/opt/ros/jazzy/share/ament_cmake/cmake) (~6725 tok)
- `streams.log` — Declares hashes (~7546 tok)

## log/build_2026-05-06_04-15-00/

- `events.log` (~10504 tok)
- `logger_all.log` (~7716 tok)

## log/build_2026-05-06_04-15-00/arm_control/

- `command.log` (~349 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~254 tok)
- `stdout.log` (~254 tok)
- `streams.log` (~650 tok)

## log/build_2026-05-06_04-15-00/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_04-18-14/

- `events.log` (~10552 tok)
- `logger_all.log` (~7636 tok)

## log/build_2026-05-06_04-18-14/arm_control/

- `command.log` (~269 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~254 tok)
- `stdout.log` (~254 tok)
- `streams.log` (~569 tok)

## log/build_2026-05-06_04-18-14/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_04-23-11/

- `events.log` (~10513 tok)
- `logger_all.log` (~7636 tok)

## log/build_2026-05-06_04-23-11/arm_control/

- `command.log` (~269 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~528 tok)

## log/build_2026-05-06_04-23-11/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_13-58-17/

- `events.log` (~10736 tok)
- `logger_all.log` (~7745 tok)

## log/build_2026-05-06_13-58-17/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~325 tok)
- `stdout.log` (~325 tok)
- `streams.log` (~752 tok)

## log/build_2026-05-06_13-58-17/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_14-13-34/

- `events.log` (~10615 tok)
- `logger_all.log` (~7745 tok)

## log/build_2026-05-06_14-13-34/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~253 tok)
- `stdout.log` (~253 tok)
- `streams.log` (~675 tok)

## log/build_2026-05-06_14-13-34/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_14-52-22/

- `events.log` (~10330 tok)
- `logger_all.log` (~7692 tok)

## log/build_2026-05-06_14-52-22/arm_control/

- `command.log` (~423 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~252 tok)
- `stdout.log` (~252 tok)
- `streams.log` (~720 tok)

## log/build_2026-05-06_14-52-22/arm_interfaces/

- `command.log` (~181 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~4962 tok)

## log/build_2026-05-06_14-54-59/

- `events.log` (~10558 tok)
- `logger_all.log` (~7745 tok)

## log/build_2026-05-06_14-54-59/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-06_14-54-59/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_14-57-09/

- `events.log` (~10558 tok)
- `logger_all.log` (~7745 tok)

## log/build_2026-05-06_14-57-09/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-06_14-57-09/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_15-00-29/

- `events.log` (~10558 tok)
- `logger_all.log` (~7745 tok)

## log/build_2026-05-06_15-00-29/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-06_15-00-29/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_15-04-23/

- `events.log` (~10558 tok)
- `logger_all.log` (~7745 tok)

## log/build_2026-05-06_15-04-23/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-06_15-04-23/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-06_15-19-50/

- `events.log` (~10549 tok)
- `logger_all.log` (~7745 tok)

## log/build_2026-05-06_15-19-50/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-06_15-19-50/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_11-38-15/

- `events.log` (~10352 tok)
- `logger_all.log` (~7692 tok)

## log/build_2026-05-07_11-38-15/arm_control/

- `command.log` (~423 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~682 tok)

## log/build_2026-05-07_11-38-15/arm_interfaces/

- `command.log` (~181 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~4962 tok)

## log/build_2026-05-07_11-52-06/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_11-52-06/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_11-52-06/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_13-15-51/

- `events.log` (~10554 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_13-15-51/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_13-15-51/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_15-48-35/

- `events.log` (~10618 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_15-48-35/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~252 tok)
- `stdout.log` (~252 tok)
- `streams.log` (~675 tok)

## log/build_2026-05-07_15-48-35/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_17-44-23/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_17-44-23/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_17-44-23/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_18-14-52/

- `events.log` (~10566 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_18-14-52/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_18-14-52/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_18-29-21/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_18-29-21/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_18-29-21/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_18-32-08/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_18-32-08/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_18-32-08/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_18-32-58/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_18-32-58/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_18-32-58/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_18-36-19/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_18-36-19/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_18-36-19/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_18-37-19/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_18-37-19/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_18-37-19/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_18-40-53/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_18-40-53/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_18-40-53/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-01-17/

- `events.log` (~10617 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-01-17/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~252 tok)
- `stdout.log` (~252 tok)
- `streams.log` (~675 tok)

## log/build_2026-05-07_19-01-17/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-08-35/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-08-35/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-08-35/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-10-40/

- `events.log` (~10559 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-10-40/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-10-40/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-12-56/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-12-56/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-12-56/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-25-24/

- `events.log` (~10559 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-25-24/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-25-24/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-29-19/

- `events.log` (~10559 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-29-19/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-29-19/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-31-26/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-31-26/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-31-26/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-44-57/

- `events.log` (~10567 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-44-57/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-44-57/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-49-39/

- `events.log` (~10559 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-49-39/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)

## log/build_2026-05-07_19-49-39/arm_interfaces/

- `command.log` (~244 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~4430 tok)
- `stdout.log` (~4430 tok)
- `streams.log` (~5024 tok)

## log/build_2026-05-07_19-49-47/

- `events.log` (~10559 tok)
- `logger_all.log` (~9867 tok)

## log/build_2026-05-07_19-49-47/arm_control/

- `command.log` (~378 tok)
- `stderr.log` (~0 tok)
- `stdout_stderr.log` (~216 tok)
- `stdout.log` (~216 tok)
- `streams.log` (~636 tok)
