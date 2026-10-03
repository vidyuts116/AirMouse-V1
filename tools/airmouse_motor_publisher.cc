#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <thread>

#include <gz/msgs/actuators.pb.h>
#include <gz/transport/Node.hh>

namespace
{
std::atomic<bool> running{true};
std::atomic<bool> sendZero{false};
void Stop(int)
{
  running.store(false);
}
void Zero(int)
{
  sendZero.store(true);
}
}

int main(int argc, char **argv)
{
  if (argc != 3)
  {
    std::cerr << "usage: publisher SPEED_RAD_S RATE_HZ\n";
    return 2;
  }
  const double speed = std::atof(argv[1]);
  const double rate = std::atof(argv[2]);
  if (speed < 0 || rate <= 0)
  {
    std::cerr << "speed must be nonnegative and rate must be positive\n";
    return 2;
  }

  std::signal(SIGINT, Stop);
  std::signal(SIGTERM, Stop);
  std::signal(SIGUSR1, Zero);
  gz::transport::Node node;
  auto publisher = node.Advertise<gz::msgs::Actuators>(
      "/airmouse/gazebo/command/motor_speed");
  if (!publisher)
  {
    std::cerr << "could not advertise actuator topic\n";
    return 1;
  }

  gz::msgs::Actuators message;
  for (int i = 0; i < 4; ++i)
    message.add_velocity(speed);

  // The Python diagnostic already established four motor-model subscribers.
  // Transport connection callbacks can lag that audit, so do not gate sends
  // on HasConnections(); repeated publication gives the subscriptions time
  // to connect without requiring another discovery query.
  const auto period = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
      std::chrono::duration<double>(1.0 / rate));
  auto next = std::chrono::steady_clock::now();
  while (running.load())
  {
    if (sendZero.exchange(false))
    {
      for (int i = 0; i < 4; ++i)
        message.set_velocity(i, 0.0);
    }
    publisher.Publish(message);
    next += period;
    std::this_thread::sleep_until(next);
  }
  return 0;
}
