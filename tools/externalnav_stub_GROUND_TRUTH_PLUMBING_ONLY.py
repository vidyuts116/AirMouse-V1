#!/usr/bin/env python3
"""
######################################################################################################
#  GROUND-TRUTH-DERIVED, PLUMBING TEST ONLY.                                                         #
#  This stub fabricates "odometry" from the Gazebo ground-truth pose plus synthetic noise and drift. #
#  It exists only to exercise ArduPilot's ExternalNav (VISO / EK3 source 6) plumbing in SITL.        #
#  It MUST be removed once Doshi's SLAM odometry exists. NEVER use it as the navigation solution,    #
#  never in performance claims, and never outside simulation.                                        #
######################################################################################################

Sends MAVLink ODOMETRY (frame_id MAV_FRAME_LOCAL_FRD, child_frame_id MAV_FRAME_BODY_FRD, the only frames
ArduPilot 4.6.3 accepts: GCS_Common.cpp:3876-3910) to ArduCopter SITL, at --rate Hz:
  * local frame = the vehicle's body FRD frame at the first received pose (SLAM-like: origin and heading
    at start), position in m, quaternion body-FRD -> local-FRD, velocity in body FRD (ArduPilot rotates it
    by q), body rates, diagonal pose/velocity covariance (variances), quality 0-100.
  * noise (PROVISIONAL assumptions, not a model of any real SLAM): white position, attitude, velocity
    noise plus slow random-walk drift on x/y/z and yaw (seeded).
Also sends SET_GPS_GLOBAL_ORIGIN (no GPS) so the EKF has an origin.
SIGUSR1 toggles a dropout (stop/resume sending) to test loss of ExternalNav.
"""

import argparse
import importlib.util
import math
import os
import signal
import sys
import time
from pathlib import Path

import numpy as np
from pymavlink import mavutil

ROOT = Path(__file__).resolve().parent.parent
LABEL = "GROUND-TRUTH-DERIVED, PLUMBING TEST ONLY"


def load(name):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quat_to_R(q):          # q = (x, y, z, w)
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def R_to_quat_wxyz(R):
    w = math.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = math.copysign(math.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0])
    z = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return [w / n, x / n, y / n, z / n]


def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def Rxyz(r, p, y):          # small-angle noise rotation
    cr, sr, cp, sp = math.cos(r), math.sin(r), math.cos(p), math.sin(p)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    return Rz(y) @ Ry @ Rx


F = np.diag([1.0, -1.0, -1.0])   # FLU <-> FRD


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mavlink", default="tcp:127.0.0.1:5762")
    parser.add_argument("--rate", type=float, default=30.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--pos-sigma", type=float, default=0.02, help="white position noise, m")
    parser.add_argument("--att-sigma-deg", type=float, default=0.3, help="white roll/pitch noise, deg")
    parser.add_argument("--yaw-sigma-deg", type=float, default=0.5, help="white yaw noise, deg")
    parser.add_argument("--vel-sigma", type=float, default=0.05, help="white velocity noise, m/s")
    parser.add_argument("--drift-xy", type=float, default=0.005, help="x/y random-walk drift, m/sqrt(s)")
    parser.add_argument("--drift-z", type=float, default=0.003, help="z random-walk drift, m/sqrt(s)")
    parser.add_argument("--drift-yaw-deg", type=float, default=0.02, help="yaw random-walk drift, deg/sqrt(s)")
    parser.add_argument("--origin", default="-35.363261,149.165230,584", help="EKF origin lat,lon,alt(m)")
    parser.add_argument("--log", required=True, help="CSV of sent odometry and truth")
    args = parser.parse_args()
    print(f"*** {LABEL} *** ExternalNav stub starting (seed {args.seed}); must be removed once Doshi's SLAM exists",
          flush=True)
    reg = load("airmouse_regression.py")
    streams = reg.Streams(reg.gz_bin())
    rng = np.random.default_rng(args.seed)
    dropout = {"on": False, "events": []}

    def toggle(signum, frame):
        dropout["on"] = not dropout["on"]
        p = streams.latest()
        dropout["events"].append((time.monotonic(), p[0] if p else float("nan"), dropout["on"]))
        print(f"*** {LABEL} *** ExternalNav dropout {'STARTED' if dropout['on'] else 'ENDED'} at sim t="
              f"{p[0] if p else float('nan'):.2f}", flush=True)

    signal.signal(signal.SIGUSR1, toggle)
    running = {"on": True}
    signal.signal(signal.SIGTERM, lambda s, f: running.update(on=False))

    mav = mavutil.mavlink_connection(args.mavlink, source_system=1, source_component=197)   # 197 = VIO component
    mav.wait_heartbeat(timeout=60)
    lat, lon, alt = (float(v) for v in args.origin.split(","))
    t_start = time.monotonic()
    while streams.latest() is None and time.monotonic() - t_start < 30:
        time.sleep(0.05)
    p0 = streams.latest()
    R0 = quat_to_R(p0[4:8]) @ F                          # local FRD axes expressed in Gazebo ENU
    pos0 = np.array(p0[1:4])
    drift = np.zeros(3)
    drift_yaw = 0.0
    prev = None
    period = 1.0 / args.rate
    next_t = time.monotonic()
    last_origin = 0.0
    sent = 0
    out = open(args.log, "w")
    out.write(f"# {LABEL}\nwall_s,sim_t,dropout,x,y,z,yaw_deg,vx,vy,vz,true_x,true_y,true_z,true_yaw_deg\n")
    while running["on"]:
        now = time.monotonic()
        if now - t_start < 30 and now - last_origin > 2.0:
            mav.mav.set_gps_global_origin_send(mav.target_system, int(lat * 1e7), int(lon * 1e7), int(alt * 1000),
                                               int(now * 1e6))
            last_origin = now
        p = streams.latest()
        dt = period
        drift += rng.normal(0, 1, 3) * np.array([args.drift_xy, args.drift_xy, args.drift_z]) * math.sqrt(dt)
        drift_yaw += rng.normal(0, 1) * math.radians(args.drift_yaw_deg) * math.sqrt(dt)
        R_enu_flu = quat_to_R(p[4:8])
        R_l_b = R0.T @ R_enu_flu @ F                       # body FRD -> local FRD (truth)
        pos_l = R0.T @ (np.array(p[1:4]) - pos0)           # truth position in local FRD
        if prev is not None and p[0] > prev[0]:
            v_enu = (np.array(p[1:4]) - np.array(prev[1:4])) / (p[0] - prev[0])
            w = R_l_b.T @ R0.T @ v_enu                     # truth velocity in body FRD
            vel_b = w
        else:
            vel_b = np.zeros(3)
        if prev is None or p[0] > prev[0]:
            prev = p
        # Measured = truth + drift + white noise (local frame), yaw drift applied about local z.
        Rd = Rz(drift_yaw)
        meas_pos = Rd @ pos_l + drift + rng.normal(0, args.pos_sigma, 3)
        noise_R = Rxyz(*(rng.normal(0, 1, 3) * np.radians([args.att_sigma_deg, args.att_sigma_deg, args.yaw_sigma_deg])))
        meas_R = Rd @ R_l_b @ noise_R
        meas_vel = vel_b + rng.normal(0, args.vel_sigma, 3)
        q = R_to_quat_wxyz(meas_R)
        if not dropout["on"]:
            pos_var = args.pos_sigma ** 2
            att_var = math.radians(args.att_sigma_deg) ** 2
            yaw_var = math.radians(args.yaw_sigma_deg) ** 2
            pose_cov = [float("nan")] * 21
            vel_cov = [float("nan")] * 21
            for i, v in zip((0, 6, 11, 15, 18, 20), (pos_var, pos_var, pos_var, att_var, att_var, yaw_var)):
                pose_cov[i] = v
            for i in (0, 6, 11):
                vel_cov[i] = args.vel_sigma ** 2
            for i in range(21):
                if math.isnan(pose_cov[i]):
                    pose_cov[i] = 0.0
                if math.isnan(vel_cov[i]):
                    vel_cov[i] = 0.0
            mav.mav.odometry_send(int(now * 1e6), mavutil.mavlink.MAV_FRAME_LOCAL_FRD, mavutil.mavlink.MAV_FRAME_BODY_FRD,
                                  float(meas_pos[0]), float(meas_pos[1]), float(meas_pos[2]), q,
                                  float(meas_vel[0]), float(meas_vel[1]), float(meas_vel[2]),
                                  float("nan"), float("nan"), float("nan"), pose_cov, vel_cov, 0,
                                  mavutil.mavlink.MAV_ESTIMATOR_TYPE_VIO, 100)
            sent += 1
        yaw_m = math.degrees(math.atan2(meas_R[1, 0], meas_R[0, 0]))
        yaw_t = math.degrees(math.atan2(R_l_b[1, 0], R_l_b[0, 0]))
        out.write(f"{now - t_start:.3f},{p[0]:.3f},{int(dropout['on'])},{meas_pos[0]:.4f},{meas_pos[1]:.4f},"
                  f"{meas_pos[2]:.4f},{yaw_m:.3f},{meas_vel[0]:.4f},{meas_vel[1]:.4f},{meas_vel[2]:.4f},"
                  f"{pos_l[0]:.4f},{pos_l[1]:.4f},{pos_l[2]:.4f},{yaw_t:.3f}\n")
        mav.recv_match(blocking=False)           # keep the link drained
        next_t += period
        time.sleep(max(0.0, next_t - time.monotonic()))
    out.close()
    streams.stop()
    print(f"*** {LABEL} *** stub stopped after {sent} ODOMETRY messages; dropout events {dropout['events']}",
          flush=True)


if __name__ == "__main__":
    sys.exit(main())
