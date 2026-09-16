import rclpy
from rclpy.node import Node
from px4_msgs.msg import VehicleCommand
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

class ArmAndTakeoff(Node):
    def __init__(self):
        super().__init__('arm_and_takeoff')
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.publisher = self.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', qos_profile)
        self.timer = self.create_timer(1.0, self.send_commands)
        self.step = 0

    def send_commands(self):
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True

        if self.step == 0:
            # 1. Send Arm Command (MAV_CMD_COMPONENT_ARM_DISARM)
            msg.command = 400
            msg.param1 = 1.0  # 1 to arm, 0 to disarm
            self.publisher.publish(msg)
            self.get_logger().info("Sent ARM command...")
            self.step += 1
        elif self.step == 1:
            # 2. Send Takeoff Command (MAV_CMD_NAV_TAKEOFF)
            msg.command = 22
            msg.param7 = 1.0  # Altitude in meters
            self.publisher.publish(msg)
            self.get_logger().info("Sent TAKEOFF command...")
            self.step += 1
        else:
            # Stop timer after commands are sent
            self.timer.cancel()

def main(args=None):
    rclpy.init(args=args)
    node = ArmAndTakeoff()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
