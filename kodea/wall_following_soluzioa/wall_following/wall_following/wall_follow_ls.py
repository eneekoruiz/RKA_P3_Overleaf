#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robotika eta Kontrol Adimendunak — 3. Proiektua
Paretari jarraitzeko nodoa laser bidezko erregresio linealarekin eta PID kontrolagailuarekin.

Egileak: Eneko Ruiz, Eneko Pardavila, Omar Ouinas
Irakaslea: Elena Lazkano (UPV/EHU)
Ingurunea: ROS 2 Humble · Gazebo (yahboom_track)
"""

import math as m
import os
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist


class WallFollowerPID(Node):
    """
    Gazeboko yahboom_track zirkuituan eskuineko paretari paralelo jarraitzeko
    PID kontrolagailua inplementatzen duen ROS 2 nodoa.
    """

    def __init__(self):
        super().__init__('wall_following_node')

        # Kontrol-parametroak eta konfigurazioa
        self.declare_parameters(
            namespace='',
            parameters=[
                ('kp', 1.5),                        # Proportzional irabazia
                ('ki', 0.0),                        # Integral irabazia
                ('kd', 0.0),                        # Deribatu irabazia
                ('output_filename', 'wf_ls'),       # Fitxategiaren aurrizkia
                ('lidar_type', 's2'),               # Lidar mota: s2, a1, turtle
                ('target_dist', 0.45),              # Paretarekiko distantzia ideala (m)
                ('v_max', 0.35),                    # Abiadura lineal maximoa (m/s)
                ('w_max', 1.5),                     # Abiadura angeluar maximoa (rad/s)
                ('use_distance_bias', True),        # Anguluaz gain distantziaren zuzenketa gehitu
            ]
        )

        self.kp = float(self.get_parameter('kp').value)
        self.ki = float(self.get_parameter('ki').value)
        self.kd = float(self.get_parameter('kd').value)
        self.output_filename = self.get_parameter('output_filename').value
        self.lidar_type = self.get_parameter('lidar_type').value
        self.target_dist = float(self.get_parameter('target_dist').value)
        self.v_max = float(self.get_parameter('v_max').value)
        self.w_max = float(self.get_parameter('w_max').value)
        self.use_distance_bias = bool(self.get_parameter('use_distance_bias').value)

        # Harpidetzak eta argitaratzaileak
        self.laser_sub = self.create_subscription(LaserScan, 'scan', self.follow_wall, 1)
        self.vel_pub = self.create_publisher(Twist, 'cmd_vel', 1)

        # Laser-eskaneatzearen barne egoera
        self.scan_count = 0
        self.scan_mid = 0
        self.max_range = 8.0
        self.bearings = []
        self.scan = []
        self.uninitialized = True

        # PID barne-aldagaiak
        self.prev_error = 0.0
        self.error_sum = 0.0
        self.prev_time = None
        self.integral_limit = 1.0   # Anti-windup muga integratzailearentzat

        # Telemetria eta grafikoetarako datuak
        self.timestamps = []
        self.data_angular_error = []
        self.data_angular_w = []
        self.data_linear_v = []
        self.data_wall_distance = []
        self.start_time = self.get_clock().now()

        # Emaitzen bidea
        home_dir = os.environ.get('HOME', os.path.expanduser('~'))
        self.results_path = os.path.join(home_dir, 'robotics_ws', 'src', 'behavior', 'wall_following', 'results')
        self.get_logger().info(
            f"[HASIERATUTA] Kp={self.kp:.3f}, Ki={self.ki:.3f}, Kd={self.kd:.3f} | Lidar: {self.lidar_type}"
        )

    def follow_wall(self, scan_msg: LaserScan):
        """LaserScan mezu bakoitzean exekutatzen den kontrol-begizta nagusia."""
        current_time = self.get_clock().now()
        dt = (current_time - self.prev_time).nanoseconds / 1e9 if self.prev_time else 0.1
        if dt <= 0.0 or dt > 0.5:
            dt = 0.1
        self.prev_time = current_time

        # 1. LaserScan konfigurazioa hasieratu lehenengo iterazioan
        if self.uninitialized:
            self.uninitialized = False
            self.scan_count = len(scan_msg.ranges)
            self.scan_mid = self.scan_count // 2
            self.max_range = scan_msg.range_max
            # Angeluen taula (bearings) aurrerantz = 0 rad erreferentziarekin
            for i in range(self.scan_count):
                self.bearings.append(scan_msg.angle_min + scan_msg.angle_increment * i)

        # Infinituak eta neurketa baliogabeak iragazi
        self.scan = [x if (scan_msg.range_min < x < self.max_range) else self.max_range for x in scan_msg.ranges]

        # S2 sentsorearen indizeak berrantolatu: 0 indizea robotaren atzealdea da
        if self.lidar_type == "s2":
            reordered_scan = [self.scan[i - self.scan_mid] for i in range(self.scan_count)]
        else:
            reordered_scan = [self.scan[self.scan_mid - i] for i in range(self.scan_count)]

        # 2. ESKUINEKO PARETAREN PROIEKZIO KARTESIARRA
        # Eskuineko sektorea hautatu: angeluak [-125º, -35º] inguruan robotaren erreferentzian
        xpos = []
        ypos = []
        front_min_dist = self.max_range

        for i in range(self.scan_count):
            angle = self.bearings[i]
            dist = reordered_scan[i]

            # Aurrealdeko segurtasun-distantzia neurtu ([-20º, +20º]) talkak saihesteko
            if -0.35 < angle < 0.35:
                if dist < front_min_dist:
                    front_min_dist = dist

            # Eskuinaldeko paretaren izpiak: angelua negatiboa eta neurketa hurbila (< 1.8 m)
            if -2.18 < angle < -0.52:   # -125º eta -30º artean
                if dist < 1.8:          # Bidearen zabalera kontuan hartuta
                    x_i = dist * m.cos(angle)
                    y_i = dist * m.sin(angle)
                    xpos.append(x_i)
                    ypos.append(y_i)

        cmd_vel_msg = Twist()
        wall_dist = self.target_dist

        # 3. ERREGRESIO LINEALA ETA KONTROL EKINTZA
        if len(xpos) >= 6:
            xcoord = np.array(xpos)
            ycoord = np.array(ypos)

            # y = c1 * x + c0 (c1: malda / slope, c0: ordenatua jatorrian / intercept)
            c1, c0 = np.polyfit(xcoord, ycoord, 1)

            # Robotaren eta paretaren arteko angelua: theta = arctan(c1)
            # Paretarekiko paralelo egoteko desiatutako angelua: desired_theta = 0.0
            theta = float(np.arctan(c1))
            desired_theta = 0.0

            # Eskuineko paretarainoko distantzia erreala kalkulatu (|c0| / sqrt(1 + c1^2))
            wall_dist = abs(c0) / m.sqrt(1.0 + c1 * c1)

            # Oinarrizko errore angeluarra: theta > 0 denean robota paretara hurbiltzen ari da
            angular_error = theta - desired_theta

            # Aukerakoa: distantzia-zuzenketa gehitu paretatik gehiegi ez aldentzeko / ez hurbiltzeko
            # Errore konbinatua: errorea = errore_angeluarra + K_d * (distantzia_erreala - distantzia_desiatua)
            if self.use_distance_bias:
                dist_error = wall_dist - self.target_dist
                # Paretatik urrunegi bagaude (dist_error > 0), eskuinera jo behar dugu (angelua txikitu)
                # Paretatik gertuegi bagaude (dist_error < 0), ezkerrera jo behar dugu (angelua handitu)
                combined_error = angular_error - 0.75 * np.clip(dist_error, -0.4, 0.4)
            else:
                combined_error = angular_error

            # --- PID KONTROLAGAILEAREN FORMULAZIOA ---
            # 1. Osagai proportzionala (P)
            prop = self.kp * combined_error

            # 2. Osagai integrala (I) + Anti-Windup saturazioa
            self.error_sum += combined_error * dt
            self.error_sum = float(np.clip(self.error_sum, -self.integral_limit, self.integral_limit))
            integ = self.ki * self.error_sum

            # 3. Osagai deribatua (D) iragazita
            deriv = self.kd * ((combined_error - self.prev_error) / dt)
            self.prev_error = combined_error

            # Abiadura angeluar osoa: w = P + I + D
            w = prop + integ + deriv
            w = float(np.clip(w, -self.w_max, self.w_max))

            # Abiadura lineala: biraketa zorrotzetan abiadura moteldu
            turn_ratio = min(1.0, abs(w) / self.w_max)
            v = self.v_max * (1.0 - 0.65 * turn_ratio)

            # Aurreko segurtasun-zuzenketa: aurrean oztopoa badago (< 0.45 m), balaztatu eta biratu
            if front_min_dist < 0.45:
                v = 0.08
                w = max(w, 0.75)  # Ezkerrerantz biratu indarrez

            cmd_vel_msg.linear.x = float(v)
            cmd_vel_msg.angular.z = float(w)

            self.get_logger().info(
                f"Slope: {c1:+.2f} | Theta: {m.degrees(theta):+5.1f}º | Dist: {wall_dist:.2f}m | "
                f"v: {v:.2f} m/s | w: {w:+.2f} rad/s"
            )
            reported_error = float(combined_error)
        else:
            # Izpi gutxiegi erregresio fidagarrirako: poliki aurrera egin paretaren bila
            self.get_logger().warn("[KONTUZ] Ez dago nahikoa izpi paretaren erregresiorako!")
            cmd_vel_msg.linear.x = 0.15
            cmd_vel_msg.angular.z = -0.15  # Pixka bat eskuinera jo paretaren bila
            reported_error = 0.0

        # Telemetria gorde
        elapsed = (current_time - self.start_time).nanoseconds / 1e9
        self.timestamps.append(elapsed)
        self.data_angular_error.append(reported_error)
        self.data_angular_w.append(cmd_vel_msg.angular.z)
        self.data_linear_v.append(cmd_vel_msg.linear.x)
        self.data_wall_distance.append(wall_dist)

        # Agindua robotari argitaratu
        self.vel_pub.publish(cmd_vel_msg)

    def save_error(self):
        """Exekuzioa amaitzean telemetria-grafikoak sortzen eta gordetzen ditu."""
        if len(self.timestamps) < 5:
            return

        elapsed = self.get_clock().now() - self.start_time
        total_sec = elapsed.nanoseconds / 1e9
        formatted_time = f"{int(total_sec // 60):02d}:{int(total_sec % 60):02d}"

        # Irudiaren tamaina eta ardatzak
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)

        t = np.array(self.timestamps)
        err = np.array(self.data_angular_error)
        w = np.array(self.data_angular_w)
        v = np.array(self.data_linear_v)
        dist = np.array(self.data_wall_distance)

        # 1. Grafikoa: Errore angeluarra eta abiadurak
        ax1.plot(t, err, label=r'Errorea $e(t)$ (rad)', color='blue', linewidth=1.2)
        ax1.plot(t, w, label=r'$\omega(t)$ (rad/s)', color='red', linestyle='--', linewidth=1.0)
        ax1.plot(t, v, label=r'$v(t)$ (m/s)', color='purple', linestyle=':', linewidth=1.0)
        ax1.set_ylabel("Balioak (rad, rad/s, m/s)")
        ax1.set_title(
            f"Paretari jarraitzeko PID erantzuna (Kp={self.kp:.2f}, Ki={self.ki:.2f}, Kd={self.kd:.2f}) — Iraupena: {formatted_time}"
        )
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax1.legend(loc='upper right')

        # 2. Grafikoa: Paretarekiko distantzia
        ax2.plot(t, dist, label='Distantzia erreala (m)', color='green', linewidth=1.2)
        ax2.axhline(self.target_dist, color='darkorange', linestyle='--', label=f'Distantzia desiatua ({self.target_dist} m)')
        ax2.set_xlabel("Denbora (s)")
        ax2.set_ylabel("Distantzia (m)")
        ax2.grid(True, linestyle='--', alpha=0.6)
        ax2.legend(loc='upper right')

        os.makedirs(self.results_path, exist_ok=True)
        now = datetime.now().strftime("%d-%m-%Y-%H_%M_%S")
        filename = f"pid_ebaluazioa_kp{self.kp:.2f}_ki{self.ki:.2f}_kd{self.kd:.2f}_{now}.png"
        out_file = os.path.join(self.results_path, filename)
        fig.tight_layout()
        plt.savefig(out_file, dpi=150)
        plt.close(fig)
        self.get_logger().info(f"[OK] Grafikoa ondo gorde da: {out_file}")


def main(args=None):
    rclpy.init(args=args)
    node = WallFollowerPID()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Gelditze-seinalea jaso da (Ctrl+C)")
    finally:
        node.save_error()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
