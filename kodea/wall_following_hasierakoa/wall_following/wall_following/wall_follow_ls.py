#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
import numpy as np
import math as m
import matplotlib.pyplot as plt
import os
from datetime import datetime

class Robot(Node):
    def __init__(self):
        super().__init__('wall_following_node')
        # kp, ki, kd value to use in the execution
        self.declare_parameters(
            namespace='',
            parameters=[
                ('kp', 1.5),
                ('ki', 0.0),
                ('kd', 0.0),
                ('output_filename', 'wf_ls'),
                ('lidar_type', 's2') # Options: a1, s2, turtle
            ]
        )
        self.kp = self.get_parameter('kp').value
        self.ki = self.get_parameter('ki').value
        self.kd = self.get_parameter('kd').value
        
        self.lidar_type = self.get_parameter('lidar_type').value

        self.laser_sub = self.create_subscription(LaserScan, 'scan', self.follow_wall, 1)
        self.vel_pub = self.create_publisher(Twist, "cmd_vel", 1)
        
        self.scan_count = 0
        self.range_min = 0.0
        self.scan_mid = 0.0
        self.max_range = 8.0
        self.bearings = []
        self.scan = []
        self.uninitialized = True

        # Initialize variables
        self.data_angular_error = []
        self.timestamps = []
        self.data_angular_w = []
        self.data_linear_v = []
        self.start_time = self.get_clock().now()
        # Paths for saving results
        package_src_root = os.path.join(os.environ['HOME'], 'robotics_ws', 'src', 'behavior', 'wall_following')
        self.results_path = os.path.join(package_src_root, 'results')
        self.get_logger().info("Results will be saved in: " + self.results_path)


        # PID
        self.error_sum = 0.0
        self.prev_error = 0.0
        

    def follow_wall(self, scan): 
        cmd_vel_msg = Twist()            
        if self.uninitialized:
            self.uninitialized = 0
            self.scan_count = len(scan.ranges)
            self.scan_mid = self.scan_count // 2
            self.max_range = scan.range_max
            # Bearings stores the angle of each range measurement (radians)
            for i in range(0, self.scan_count):
                self.bearings.append(scan.angle_min + scan.angle_increment * i)
            
        # Replace infinity values with max_range 
        self.scan = [x if x < self.max_range else self.max_range for x in scan.ranges]        
        self.get_logger().info("scan len: %.2f "%(len(self.scan)))
        # Reorganize scan indexes to make it easier to work with. 
        # 0 index corresponds to the back side of the robot for both, scan and bearings.
        if self.lidar_type == "s2":
            self.get_logger().info("scan_mid: %.2f "%(self.scan_mid))
            self.scan = [self.scan[i - self.scan_mid] for i in range(self.scan_count)]
            

        else:
            self.scan = [self.scan[self.scan_mid-i] for i in range(self.scan_count)]
       
        
        ## TODO Add code here
        # 1.- Compute the projection of short readings 
        xpos = []
        ypos = []

        # Select the short readings and calculate the corresponding points
        

        # Store the values for plotting
        elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
        self.timestamps.append(elapsed)

        # 2.- Linear regression: compute the line from the selected points   
        if len(xpos) > 5: 
            # Note: The len(xpos) value indicates the number of points used in the regression!!
            xcoord = np.array(xpos)
            ycoord = np.array(ypos)

            # Use Numpy polifyt for liner regression
            c1, c0 = np.polyfit(xcoord, ycoord, 1) # c1: slope; c0:intercept

	        # Fake value, needs to be defined
            desired_theta = 8.97 
            # Calculate the angle between the robot and the wall
            theta = 0.0 
            self.get_logger().info("Line slope: %.2f Angle: %.2f (%.2f degrees)"%(c1, theta, m.degrees(theta)))
           
            error = theta - desired_theta

            

            # 3.- Set velocities proportionally
            w = self.kp * error
            v = 0.0
            self.get_logger().info("Velocities: v = %.2f w = %.2f"%(v, w))
            ## END TODO

            cmd_vel_msg.linear.x  = v
            cmd_vel_msg.linear.y  = 0.0
            cmd_vel_msg.angular.z = w

        else:
            self.get_logger().info("Not enough points for applying the linear regression")
            cmd_vel_msg.linear.x  = 0.2
            cmd_vel_msg.linear.y  = 0.0
            cmd_vel_msg.angular.z = 0.0

        # Fake value, replace by calculated angular value
        self.data_angular_error.append(8.97) 
        self.data_angular_w.append(cmd_vel_msg.angular.z)   
        self.data_linear_v.append(cmd_vel_msg.linear.x)
        self.vel_pub.publish( cmd_vel_msg)

    def save_error(self):
        # Calculate elapsed time
        elapsed = self.get_clock().now() - self.start_time
        total_ms = elapsed.nanoseconds // 1_000_000  # milisegundos totales
        minutes = (total_ms // 1000) // 60
        seconds = (total_ms // 1000) % 60
        milliseconds = total_ms % 1000
        formatted_time = f"{minutes:02}:{seconds:02}.{milliseconds:03}" # Format MM:SS.MS

        # Create the plot
        plt.figure()
        plt.ylim(-np.pi/2, np.pi/2)
        plt.xlabel("Time (s)")
        plt.ylabel("Error (pixels)")
        plt.title(f"Error over time (Kp={self.kp:.2f}, Ki={self.ki:.2f}, Kd={self.kd:.2f}) \n")
        
        # Plot only the first 60 seconds
        timestamps = np.array(self.timestamps)
        error_x = np.array(self.data_angular_error)
        angular_w = np.array(self.data_angular_w)
        linear_v = np.array(self.data_linear_v)
        mask = timestamps < 60.0
        plt.plot(timestamps[mask], error_x[mask], linestyle='-', color='g', linewidth=0.5)
        plt.plot(timestamps[mask], angular_w[mask], linestyle='-', color='r', linewidth=0.5)
        plt.plot(timestamps[mask], linear_v[mask], linestyle='-', color='m', linewidth=0.5)
        plt.grid(True, which='both', linestyle='--', color='gray', alpha=0.7)
        # Draw the legend
        plt.legend(['Error', 'w', 'v'])

        # Draw elapsed time
        fig = plt.gcf()
        fig.text(
            0.5, 0.9,  
            f"Elapsed time: {formatted_time}",
            ha='center',
            va='top',
            fontsize=10,
            bbox=dict(facecolor='white', edgecolor='black', boxstyle='round,pad=0.2')
        )

        # Check if results folder exists
        if not os.path.exists(self.results_path):
            os.makedirs(self.results_path)

        # Get date and time
        now = datetime.now()
        dt_string = now.strftime("%d-%m-%Y-%H:%M:%S")
        # Format kp and kd (replace dot with underscore for filename safety)
        kp_str = f"{self.kp:.2f}".replace('.', '_')
        kd_str = f"{self.kd:.2f}".replace('.', '_')
        ki_str = f"{self.ki:.2f}".replace('.', '_')

        # Build the filename
        filename = f"error_{dt_string}-kp{kp_str}-kd{kd_str}-ki{ki_str}.png"
        plt.savefig(self.results_path +'/' + filename)
        plt.show()

def main(args=None):
    rclpy.init(args=args)
    wf_node = Robot()
    try:
        rclpy.spin(wf_node)
    except KeyboardInterrupt:
        wf_node.destroy_node()
    finally:
        wf_node.save_error()
        wf_node.destroy_node()  
        rclpy.shutdown()

if __name__ == '__main__':
    main()
