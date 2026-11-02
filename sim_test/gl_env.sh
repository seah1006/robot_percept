# source ~/work/robot_percept/sim_test/gl_env.sh  -> MuJoCo offscreen on the RTX 2080 SUPER via Mesa D3D12 (WSLg)
export MUJOCO_GL=egl
export GALLIUM_DRIVER=d3d12
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
unset PYOPENGL_PLATFORM
