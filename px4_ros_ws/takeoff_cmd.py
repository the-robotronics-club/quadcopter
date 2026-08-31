import rclpy
from rclpy.node import Node
from px4_msgs.msg import VehicleCommand
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

class TakeoffCommander(Node):
    def __init__(self):
        super().__init__('takeoff_commander')
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.publisher = self.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', qos_profile)
        
        # Send command after 2 seconds to allow connection
        self.timer = self.create_timer(2.0, self.send_command)
        self.sent = False

    def send_command(self):
        if self.sent:
            return
        
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.command = 22  # MAV_CMD_NAV_TAKEOFF
        msg.param1 = 1.0  # Minimum pitch
        msg.param7 = 1.0  # Target altitude in meters
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True

        self.publisher.publish(msg)
        self.get_logger().info("Takeoff command sent to PX4!")
        self.sent = True

def main(args=None):
    rclpy.init(args=args)
    node = TakeoffCommander()
    rclpy.spin_once(node, timeout_sec=3.0)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
