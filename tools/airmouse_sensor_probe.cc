// Subscribes to AirMouse virtual-sensor topics and prints one compact line per
// message (simulation timestamp first) for the regression tool to parse.
//   usage: airmouse_sensor_probe kind:topic [kind:topic ...]
//   kinds: imu, scan, image
// Output lines:
//   IMU <topic> <t> ax ay az gx gy gz
//   SCAN <topic> <t> <count> <angle_min> <angle_step> <range_min> <range_max> r0 r1 ...
//   IMG <topic> <t> <width> <height> <pixel_format> <step> <bytes> <centre> <mean> <std>
//     centre/mean/std: metres for R_FLOAT32 depth (finite pixels), 0-255 intensity for RGB_INT8
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>

#include <gz/msgs/image.pb.h>
#include <gz/msgs/imu.pb.h>
#include <gz/msgs/laserscan.pb.h>
#include <gz/transport/Node.hh>

namespace
{
std::mutex outMutex;

double Seconds(const gz::msgs::Header &h)
{
  return h.stamp().sec() + h.stamp().nsec() * 1e-9;
}
}  // namespace

int main(int argc, char **argv)
{
  if (argc < 2)
  {
    std::fprintf(stderr, "usage: %s kind:topic ...\n", argv[0]);
    return 2;
  }
  gz::transport::Node node;
  for (int i = 1; i < argc; ++i)
  {
    const std::string arg = argv[i];
    const auto colon = arg.find(':');
    const std::string kind = arg.substr(0, colon);
    const std::string topic = arg.substr(colon + 1);
    bool ok = false;
    if (kind == "imu")
    {
      ok = node.Subscribe<gz::msgs::IMU>(topic, [topic](const gz::msgs::IMU &m) {
        const auto &a = m.linear_acceleration();
        const auto &w = m.angular_velocity();
        std::lock_guard<std::mutex> lock(outMutex);
        std::printf("IMU %s %.6f %.9g %.9g %.9g %.9g %.9g %.9g\n", topic.c_str(), Seconds(m.header()),
                    a.x(), a.y(), a.z(), w.x(), w.y(), w.z());
        std::fflush(stdout);
      });
    }
    else if (kind == "scan")
    {
      ok = node.Subscribe<gz::msgs::LaserScan>(topic, [topic](const gz::msgs::LaserScan &m) {
        std::lock_guard<std::mutex> lock(outMutex);
        std::printf("SCAN %s %.6f %d %.9g %.9g %.9g %.9g", topic.c_str(), Seconds(m.header()),
                    m.ranges_size(), m.angle_min(), m.angle_step(), m.range_min(), m.range_max());
        for (int r = 0; r < m.ranges_size(); ++r)
          std::printf(" %.6g", m.ranges(r));
        std::printf("\n");
        std::fflush(stdout);
      });
    }
    else if (kind == "image")
    {
      ok = node.Subscribe<gz::msgs::Image>(topic, [topic](const gz::msgs::Image &m) {
        const std::string &d = m.data();
        const unsigned w = m.width(), h = m.height();
        double centre = NAN, sum = 0, sum2 = 0;
        long n = 0;
        if (m.pixel_format_type() == gz::msgs::PixelFormatType::R_FLOAT32 && d.size() >= 4ul * w * h)
        {
          auto px = [&](size_t i) { float v; std::memcpy(&v, d.data() + 4 * i, 4); return v; };
          centre = px((h / 2) * w + w / 2);
          for (size_t i = 0; i < size_t(w) * h; i += 7)
          {
            const float v = px(i);
            if (std::isfinite(v)) { sum += v; sum2 += double(v) * v; ++n; }
          }
        }
        else if (m.pixel_format_type() == gz::msgs::PixelFormatType::RGB_INT8 && d.size() >= 3ul * w * h)
        {
          const size_t c = 3 * ((h / 2) * w + w / 2);
          centre = (uint8_t(d[c]) + uint8_t(d[c + 1]) + uint8_t(d[c + 2])) / 3.0;
          for (size_t i = 0; i < d.size(); i += 7)
          {
            const double v = uint8_t(d[i]);
            sum += v; sum2 += v * v; ++n;
          }
        }
        const double mean = n ? sum / n : NAN;
        const double sd = n ? std::sqrt(std::max(0.0, sum2 / n - mean * mean)) : NAN;
        std::lock_guard<std::mutex> lock(outMutex);
        std::printf("IMG %s %.6f %u %u %d %u %zu %.6g %.6g %.6g\n", topic.c_str(), Seconds(m.header()), w, h,
                    static_cast<int>(m.pixel_format_type()), m.step(), d.size(), centre, mean, sd);
        std::fflush(stdout);
      });
    }
    if (!ok)
    {
      std::fprintf(stderr, "could not subscribe %s\n", arg.c_str());
      return 1;
    }
  }
  std::printf("PROBE_READY\n");
  std::fflush(stdout);
  gz::transport::waitForShutdown();
  return 0;
}
