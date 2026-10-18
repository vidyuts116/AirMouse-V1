// AirMouse SITL actuator bridge (Gazebo Sim 8 system plugin).
//
// ArduPilotPlugin "COMMAND" control channels publish one gz.msgs.Double per
// motor (already scaled to rad/s). The verified MulticopterMotorModel
// instances subscribe to a single gz.msgs.Actuators vector indexed by
// actuator_number. This plugin collects the Doubles and republishes the
// whole vector whenever any channel updates. It applies no physics itself.
//
//   <plugin filename="AirMouseActuatorsBridge" name="airmouse::ActuatorsBridge">
//     <input_topic>/airmouse/sitl/rotor_0_cmd</input_topic>   <!-- actuator 0 -->
//     ... one per actuator, in actuator_number order ...
//     <output_topic>/airmouse/gazebo/command/motor_speed</output_topic>
//   </plugin>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include <gz/msgs/actuators.pb.h>
#include <gz/msgs/double.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/transport/Node.hh>

namespace airmouse
{
class ActuatorsBridge : public gz::sim::System, public gz::sim::ISystemConfigure
{
  public: void Configure(const gz::sim::Entity &, const std::shared_ptr<const sdf::Element> &_sdf,
                         gz::sim::EntityComponentManager &, gz::sim::EventManager &) override
  {
    std::vector<std::string> inputs;
    for (auto el = _sdf->FindElement("input_topic"); el; el = el->GetNextElement("input_topic"))
      inputs.push_back(el->Get<std::string>());
    const std::string output = _sdf->Get<std::string>("output_topic", "/airmouse/gazebo/command/motor_speed").first;
    if (inputs.empty())
    {
      gzerr << "[ActuatorsBridge] no <input_topic> elements; plugin disabled\n";
      return;
    }
    this->velocities.assign(inputs.size(), 0.0);
    this->pub = this->node.Advertise<gz::msgs::Actuators>(output);
    for (size_t i = 0; i < inputs.size(); ++i)
    {
      std::function<void(const gz::msgs::Double &)> cb = [this, i](const gz::msgs::Double &_msg)
      {
        gz::msgs::Actuators out;
        {
          std::lock_guard<std::mutex> lock(this->mutex);
          this->velocities[i] = _msg.data();
          for (double v : this->velocities)
            out.add_velocity(v);
        }
        this->pub.Publish(out);
      };
      if (!this->node.Subscribe(inputs[i], cb))
        gzerr << "[ActuatorsBridge] could not subscribe to " << inputs[i] << "\n";
      gzmsg << "[ActuatorsBridge] actuator " << i << " <- " << inputs[i] << "\n";
    }
    gzmsg << "[ActuatorsBridge] publishing gz.msgs.Actuators on " << output << "\n";
  }

  private: gz::transport::Node node;
  private: gz::transport::Node::Publisher pub;
  private: std::mutex mutex;
  private: std::vector<double> velocities;
};
}  // namespace airmouse

GZ_ADD_PLUGIN(airmouse::ActuatorsBridge, gz::sim::System, gz::sim::ISystemConfigure)
GZ_ADD_PLUGIN_ALIAS(airmouse::ActuatorsBridge, "airmouse::ActuatorsBridge")
