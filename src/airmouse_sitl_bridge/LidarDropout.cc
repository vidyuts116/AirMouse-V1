// AirMouse LiDAR dropout filter (Gazebo Sim 8 world/model system plugin).
//
// gpu_lidar has no dropout model. This plugin subscribes to a raw gz.msgs.LaserScan topic and republishes it
// on the contract topic with random "no return" beams (range = +inf, intensity 0, the same value gpu_lidar
// reports when a beam hits nothing within range):
//   * every beam is dropped independently with probability beam_dropout_prob;
//   * with probability scan_dropout_prob a whole scan is dropped (all beams no-return, e.g. glare/occlusion);
//   * a dropped scan is still published, so the message rate is unchanged.
// Seeded, so a run is repeatable. It applies no physics and touches nothing else.
//
//   <plugin filename="AirMouseLidarDropout" name="airmouse::LidarDropout">
//     <input_topic>/airmouse/lidar_raw</input_topic>
//     <output_topic>/airmouse/lidar</output_topic>
//     <beam_dropout_prob>0.02</beam_dropout_prob>
//     <scan_dropout_prob>0.01</scan_dropout_prob>
//     <seed>1</seed>
//   </plugin>
#include <cmath>
#include <limits>
#include <memory>
#include <mutex>
#include <random>
#include <string>

#include <gz/msgs/laserscan.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/transport/Node.hh>

namespace airmouse
{
class LidarDropout : public gz::sim::System, public gz::sim::ISystemConfigure
{
  public: void Configure(const gz::sim::Entity &, const std::shared_ptr<const sdf::Element> &_sdf,
                         gz::sim::EntityComponentManager &, gz::sim::EventManager &) override
  {
    const std::string in = _sdf->Get<std::string>("input_topic", "/airmouse/lidar_raw").first;
    const std::string out = _sdf->Get<std::string>("output_topic", "/airmouse/lidar").first;
    this->beamProb = _sdf->Get<double>("beam_dropout_prob", 0.0).first;
    this->scanProb = _sdf->Get<double>("scan_dropout_prob", 0.0).first;
    this->rng.seed(_sdf->Get<unsigned>("seed", 1u).first);
    this->pub = this->node.Advertise<gz::msgs::LaserScan>(out);
    if (!this->node.Subscribe(in, &LidarDropout::OnScan, this))
      gzerr << "[LidarDropout] could not subscribe to " << in << "\n";
    gzmsg << "[LidarDropout] " << in << " -> " << out << " beam " << this->beamProb << " scan " << this->scanProb
          << "\n";
  }

  private: void OnScan(const gz::msgs::LaserScan &_msg)
  {
    gz::msgs::LaserScan scan = _msg;
    const double inf = std::numeric_limits<double>::infinity();
    {
      std::lock_guard<std::mutex> lock(this->mutex);
      std::uniform_real_distribution<double> u(0.0, 1.0);
      const bool all = u(this->rng) < this->scanProb;
      for (int i = 0; i < scan.ranges_size(); ++i)
      {
        if (all || u(this->rng) < this->beamProb)
        {
          scan.set_ranges(i, inf);
          if (i < scan.intensities_size())
            scan.set_intensities(i, 0.0);
        }
      }
    }
    this->pub.Publish(scan);
  }

  private: gz::transport::Node node;
  private: gz::transport::Node::Publisher pub;
  private: std::mutex mutex;
  private: std::mt19937 rng;
  private: double beamProb{0.0};
  private: double scanProb{0.0};
};
}  // namespace airmouse

GZ_ADD_PLUGIN(airmouse::LidarDropout, gz::sim::System, gz::sim::ISystemConfigure)
GZ_ADD_PLUGIN_ALIAS(airmouse::LidarDropout, "airmouse::LidarDropout")
