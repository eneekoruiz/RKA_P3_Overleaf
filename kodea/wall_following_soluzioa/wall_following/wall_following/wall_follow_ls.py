#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robotika eta Kontrol Adimendunak. 3. praktika: paretari jarraitzea.

Robotak eskuineko paretari jarraitzen dio, bere mugimendua paretarekiko
paraleloa mantenduz. Ideia nagusia:

    1. Eskuineko izpien proiekzio kartesiarra:  xi = di*cos(bi),  yi = di*sin(bi)
    2. Paretaren zuzena erregresioz:            y = c0 + c1*x
    3. Robotaren eta paretaren arteko angelua:  theta = arctan(c1)
    4. Errorea:                                 e = theta - 0
    5. PID diskretua:     w = Kp*e + Ki*batura(e*dt) + Kd*(e - e_aurrekoa)/dt
    6. Abiadura lineala:  v = v0 / (1 + kv*|w|)   (kv=0 denean, konstantea)

Egileak: Eneko Ruiz, Eneko Pardavila, Omar Ouinas
Irakaslea: Elena Lazkano (UPV/EHU)
"""

import csv
import math as m
import os
import signal
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

# Paretako puntuak hautatzeko sektorea: eskuin-aurreko koadrantea (ikus enuntziatuaren
# 1. irudia). Robotaren erreferentzian 0 = aurrera eta -90 gradu = eskuina. Aurrerantz
# 0 graduraino iristen denez, aurreko pareta garaiz ikusten da eta izkina PID hutsarekin
# hartzen da, beste mekanismorik gabe.
SEKTORE_MIN = m.radians(-90.0)
SEKTORE_MAX = m.radians(0.0)

# Integralaren muga (anti-windup), rad*s-tan. Izkina guztietan errorea zeinu berekoa
# denez, mugarik gabe integrala pilatu egiten da eta zuzenetan paralelotasuna galtzen da.
I_MAX = 0.3


class Robot(Node):
    def __init__(self):
        super().__init__('wall_following_node')
        # Kontrolaren parametroak: launch fitxategitik jasotzen dira
        self.declare_parameters(
            namespace='',
            parameters=[
                ('kp', 1.5),            # Irabazi proportzionala
                ('ki', 0.0),            # Irabazi integrala
                ('kd', 0.0),            # Irabazi deribatiboa
                ('v0', 0.2),            # Oinarrizko abiadura lineala (m/s)
                ('kv', 0.0),            # Biraketetan moteltzeko irabazia (0: v konstantea)
                ('d_max', 1.2),         # Irakurketa "motzaren" muga (m)
                ('lidar_type', 's2'),   # Aukerak: a1, s2, turtle
            ]
        )
        self.kp = self.get_parameter('kp').value
        self.ki = self.get_parameter('ki').value
        self.kd = self.get_parameter('kd').value
        self.v0 = self.get_parameter('v0').value
        self.kv = self.get_parameter('kv').value
        self.d_max = self.get_parameter('d_max').value
        self.lidar_type = self.get_parameter('lidar_type').value

        self.laser_sub = self.create_subscription(LaserScan, 'scan', self.follow_wall, 1)
        self.odom_sub = self.create_subscription(Odometry, 'odom', self.save_pose, 1)
        self.vel_pub = self.create_publisher(Twist, 'cmd_vel', 1)

        self.scan_count = 0
        self.scan_mid = 0
        self.max_range = 8.0
        self.bearings = []
        self.scan = []
        self.uninitialized = True

        # PID kontrolaren memoria
        self.error_sum = 0.0        # Errorearen integrala
        self.prev_error = None      # Aurreko errorea (None: oraindik ez dago)
        self.prev_stamp = None      # Aurreko eskaneoaren denbora

        # Robotaren azken posizioa (odometriatik)
        self.x = float('nan')
        self.y = float('nan')

        # Grafikoetarako datuak: lagin bat eskaneo bakoitzean
        self.timestamps = []
        self.data_x = []
        self.data_y = []
        self.data_theta = []
        self.data_angular_w = []
        self.data_linear_v = []

        # Emaitzak gordetzeko karpeta
        package_src_root = os.path.join(os.environ['HOME'], 'robotics_ws', 'src',
                                        'behavior', 'wall_following')
        self.results_path = os.path.join(package_src_root, 'results')
        self.get_logger().info('Emaitzak hemen gordeko dira: ' + self.results_path)

    def save_pose(self, odom):
        """Odometriaren azken posizioa gorde, ibilbidea irudikatzeko."""
        self.x = odom.pose.pose.position.x
        self.y = odom.pose.pose.position.y

    def follow_wall(self, scan):
        """Kontrol-begizta: eskaneo bakoitzean paretarekiko angelua erregulatzen du."""
        cmd_vel_msg = Twist()

        # dt eskaneoaren denbora-zigilutik lortzen da: horrela simulazioaren
        # denbora erabiltzen da, Gazebo denbora errealean ez badabil ere.
        stamp = scan.header.stamp.sec + scan.header.stamp.nanosec * 1e-9
        dt = 0.0 if self.prev_stamp is None else max(stamp - self.prev_stamp, 0.0)
        self.prev_stamp = stamp

        if self.uninitialized:
            self.uninitialized = False
            self.scan_count = len(scan.ranges)
            self.scan_mid = self.scan_count // 2
            self.max_range = scan.range_max
            # bearings: irakurketa bakoitzaren angelua (radianetan)
            for i in range(0, self.scan_count):
                self.bearings.append(scan.angle_min + scan.angle_increment * i)
            # Egiaztapenerako: sektoreak (-90, 0) gradu artean espero ditu eskuineko izpiak
            self.get_logger().info('Laserra: %d izpi, %.0f eta %.0f gradu artean' % (
                self.scan_count, m.degrees(scan.angle_min), m.degrees(scan.angle_max)))

        # Balio infinituak eta baliogabeak max_range-rekin ordezkatu
        self.scan = [x if scan.range_min < x < self.max_range else self.max_range
                     for x in scan.ranges]

        # Indizeak berrantolatu: 0 indizea robotaren atzealdea da, bai scan-en
        # bai bearings-en (irakasleak emandako kodea, aldatu gabe).
        if self.lidar_type == 's2':
            self.scan = [self.scan[i - self.scan_mid] for i in range(self.scan_count)]
        else:
            self.scan = [self.scan[self.scan_mid - i] for i in range(self.scan_count)]

        # 1.- Irakurketa motzen proiekzio kartesiarra, robotaren erreferentzian:
        #     X ardatza aurrerantz eta Y ardatza ezkerrerantz.
        xpos = []
        ypos = []
        for d, beta in zip(self.scan, self.bearings):
            if SEKTORE_MIN < beta < SEKTORE_MAX and d < self.d_max:
                xpos.append(d * m.cos(beta))
                ypos.append(d * m.sin(beta))

        # 2.- Erregresio lineala: hautatutako puntuetatik paretaren zuzena
        theta = float('nan')
        if len(xpos) > 5:
            xcoord = np.array(xpos)
            ycoord = np.array(ypos)
            c1, c0 = np.polyfit(xcoord, ycoord, 1)  # c1: malda; c0: ordenatua jatorrian

            # Paretaren angelua robotaren X ardatzarekiko. Pareta paraleloa bada,
            # malda 0 da. theta > 0: robota paretara hurbiltzen ari da, eta
            # ezkerrera biratu behar du (w > 0). theta < 0: urruntzen ari da.
            theta = float(np.arctan(c1))
            desired_theta = 0.0
            error = theta - desired_theta

            # 3.- PID diskretua
            # I: errorearen batura denboran zehar, I_MAX-en mugatuta
            self.error_sum = float(np.clip(self.error_sum + error * dt, -I_MAX, I_MAX))
            if self.prev_error is None or dt <= 0.0:
                derivative = 0.0           # Lehen laginean ez dago deribaturik
            else:
                derivative = (error - self.prev_error) / dt   # D: errorearen aldaketa
            self.prev_error = error

            w = self.kp * error + self.ki * self.error_sum + self.kd * derivative

            # 4.- Abiadura lineala: konstantea (kv=0) edo |w|-ren alderantziz
            #     proportzionala (kv>0), biraketa handietan motelago joateko.
            v = self.v0 / (1.0 + self.kv * abs(w))

            self.get_logger().info('theta: %+6.1f gradu | v = %.2f | w = %+.2f'
                                   % (m.degrees(theta), v, w))
            cmd_vel_msg.linear.x = v
            cmd_vel_msg.angular.z = w
        else:
            # Paretarik ez: zuzen jarraitu hura aurkitu arte. Aurreko errorea ahaztu
            # egiten da, pareta berriz agertzean deribatu faltsurik ez kalkulatzeko.
            self.get_logger().info('Ez dago puntu nahikorik erregresiorako')
            self.prev_error = None
            cmd_vel_msg.linear.x = self.v0
            cmd_vel_msg.angular.z = 0.0

        # Lagina gorde eta agindua bidali
        self.timestamps.append(stamp)
        self.data_x.append(self.x)
        self.data_y.append(self.y)
        self.data_theta.append(theta)
        self.data_angular_w.append(cmd_vel_msg.angular.z)
        self.data_linear_v.append(cmd_vel_msg.linear.x)
        self.vel_pub.publish(cmd_vel_msg)

    def save_error(self):
        """Exekuzioaren datuak CSV batean gorde eta angeluaren grafikoa sortu."""
        if not self.timestamps:
            return
        os.makedirs(self.results_path, exist_ok=True)
        name = 'wf_kp%.2f_ki%.2f_kd%.2f_v%.2f_kv%.2f_%s' % (
            self.kp, self.ki, self.kd, self.v0, self.kv,
            datetime.now().strftime('%Y%m%d-%H%M%S'))
        base = os.path.join(self.results_path, name)
        t = np.array(self.timestamps) - self.timestamps[0]

        # CSVa lehenik: wf_plot.py-k erabiliko du konparaketa-grafikoak egiteko
        with open(base + '.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['t', 'x', 'y', 'theta', 'w', 'v'])
            writer.writerows(zip(t, self.data_x, self.data_y, self.data_theta,
                                 self.data_angular_w, self.data_linear_v))

        plt.figure()
        plt.plot(t, np.degrees(self.data_theta), 'g', linewidth=0.8)
        plt.axhline(0.0, color='gray', linewidth=0.5)
        plt.xlabel('Denbora (s)')
        plt.ylabel('theta (gradu)')
        plt.title('Kp=%.2f  Ki=%.2f  Kd=%.2f' % (self.kp, self.ki, self.kd))
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.savefig(base + '.png', dpi=150)
        self.get_logger().info('Gordeta: ' + base + '.csv')


def main(args=None):
    rclpy.init(args=args)
    wf_node = Robot()
    try:
        rclpy.spin(wf_node)
    except KeyboardInterrupt:
        pass
    finally:
        # Bigarren Ctrl+C batek ez dezala datuen gordetzea eten
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        wf_node.save_error()
        wf_node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
