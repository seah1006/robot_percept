# G-A grasp results

gate = contact-triggered weld approximation; oracle excluded.

| mode | object | success | Wilson 95% | failures |
|---|---|---|---|---|
| phys | dowel | 0/20 | 0.000 to 0.161 | {'no_contact': 18, 'ik_fail': 2} |

## Metadata

~~~json
{
  "git_commit": "b80d817a3e1aa42a56ac7e5f2b1196f2bc2a4edb",
  "git_dirty": true,
  "params": {
    "approach_height": 0.16,
    "descend_offset": 0.05,
    "close_seconds": 1.0,
    "approach_seconds": 2.0,
    "descend_seconds": 2.0,
    "lift_seconds": 1.0,
    "lift_height": 0.1,
    "hold_seconds": 2.0,
    "sample_dt": 0.02,
    "stage_timeout": 15.0,
    "waypoint_x": 0.13,
    "waypoint_height": 0.16,
    "waypoint_seconds": 2.0,
    "yaw_offset": 0.0,
    "close_settle_seconds": 1.0
  },
  "params_sha256": "e7cf25992b544c07381f5ce15c458c605d31ea830668fdb6f89f79b7d1e8dac7",
  "mujoco_version": "3.17.0",
  "seeds": [
    1000,
    1001,
    1002,
    1003,
    1004,
    1005,
    1006,
    1007,
    1008,
    1009,
    1010,
    1011,
    1012,
    1013,
    1014,
    1015,
    1016,
    1017,
    1018,
    1019
  ],
  "protocol": "G-A 2s hold >=50Hz",
  "gate_approximation": true
}
~~~
