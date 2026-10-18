// Persistent AirMouse motor-command publisher with command-latency timing.
//
// Publishes gz.msgs.Actuators on /airmouse/gazebo/command/motor_speed at a
// fixed rate, starting at 0 rad/s. Reads commands from stdin:
//   speed <rad/s>   switch all four commanded speeds (published immediately)
//   speeds a b c d  set per-actuator speeds in rad/s (published immediately)
//   status          print whether the publisher has subscriber connections
//   quit            exit
// Subscribes to the diagnostic JointStatePublisher topic and, after each
// speed change, reports the first joint-state sample whose rotor speeds are
// all non-zero, as both wall-clock and simulation-time delay.
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>

#include <gz/msgs/actuators.pb.h>
#include <gz/msgs/model.pb.h>
#include <gz/transport/Node.hh>

namespace
{
using Clock = std::chrono::steady_clock;
std::mutex mtx;
double commanded[4] = {0.0, 0.0, 0.0, 0.0};
bool awaiting = false;
Clock::time_point commandWall;
double commandSim = -1.0;   // latest joint-state sim time when the command was issued
double latestSim = -1.0;

double Seconds(const gz::msgs::Time &t) { return t.sec() + t.nsec() * 1e-9; }

void OnJointState(const gz::msgs::Model &msg)
{
  const auto wall = Clock::now();
  const double sim = Seconds(msg.header().stamp());
  int nonzero = 0;
  for (const auto &joint : msg.joint())
    if (std::fabs(joint.axis1().velocity()) > 1e-6)
      ++nonzero;
  std::lock_guard<std::mutex> lock(mtx);
  latestSim = sim;
  if (awaiting && nonzero == 4)
  {
    awaiting = false;
    const double wallDelay = std::chrono::duration<double>(wall - commandWall).count();
    std::printf("FIRST_NONZERO sim=%.6f cmd_sim=%.6f sim_delay=%.6f wall_delay=%.6f\n",
                sim, commandSim, sim - commandSim, wallDelay);
    std::fflush(stdout);
  }
}
}  // namespace

int main(int argc, char **argv)
{
  const double rate = argc > 1 ? std::atof(argv[1]) : 100.0;
  gz::transport::Node node;
  auto publisher = node.Advertise<gz::msgs::Actuators>("/airmouse/gazebo/command/motor_speed");
  if (!publisher || !node.Subscribe("/airmouse/diagnostic/joint_state", OnJointState))
  {
    std::cerr << "could not advertise/subscribe\n";
    return 1;
  }
  std::atomic<bool> running{true};
  auto publishNow = [&]() {
    gz::msgs::Actuators message;
    {
      std::lock_guard<std::mutex> lock(mtx);
      for (int i = 0; i < 4; ++i)
        message.add_velocity(commanded[i]);
    }
    publisher.Publish(message);
  };
  std::thread loop([&]() {
    const auto period = std::chrono::duration_cast<Clock::duration>(
        std::chrono::duration<double>(1.0 / rate));
    auto next = Clock::now();
    while (running.load())
    {
      publishNow();
      next += period;
      std::this_thread::sleep_until(next);
    }
  });
  std::printf("READY\n");
  std::fflush(stdout);

  std::string word;
  while (std::cin >> word)
  {
    if (word == "speed" || word == "speeds")
    {
      double values[4];
      std::cin >> values[0];
      for (int i = 1; i < 4; ++i)
        if (word == "speeds")
          std::cin >> values[i];
        else
          values[i] = values[0];
      {
        std::lock_guard<std::mutex> lock(mtx);
        bool allPositive = true;
        for (int i = 0; i < 4; ++i)
        {
          allPositive = allPositive && values[i] > 0;
          commanded[i] = values[i];
        }
        // Only time the zero-to-spinning transition.
        awaiting = allPositive && word == "speed";
        commandWall = Clock::now();
        commandSim = latestSim;
      }
      publishNow();
      std::printf("CMD speeds=%.6f,%.6f,%.6f,%.6f cmd_sim=%.6f connected=%d\n", values[0],
                  values[1], values[2], values[3], commandSim, publisher.HasConnections() ? 1 : 0);
    }
    else if (word == "status")
      std::printf("STATUS connected=%d\n", publisher.HasConnections() ? 1 : 0);
    else if (word == "quit")
      break;
    std::fflush(stdout);
  }
  running.store(false);
  loop.join();
  return 0;
}
