# Gazebo Harmonic resource and build-feasibility audit

Date: 2026-10-03  
Scope: Read-only analysis for native macOS on the AirMouse Mac. No install, uninstall, cleanup, configuration change, build, or permission change was performed.

## Baseline checked

- Apple M3, 8 GB RAM, ARM64, macOS 26.3.
- Homebrew 7.0.7 at `/opt/homebrew`; available root space: 41 GiB (`df -h /`).
- `gz-harmonic` stable 1.0.0, revision 5, in `osrf/simulation`; it has no bottle and must build from its source archive.
- Homebrew reports 17 required formula dependencies plus a build dependency on CMake. The recursive dependency closure contains 199 unique formulas; 16 are already installed and 183 are missing.
- Formula metadata and the Homebrew info output contain no source archive byte sizes, bottle byte sizes, or installed-size fields for this closure (source-size fields present: 0/199; installed-size fields: 0/199). Therefore Homebrew cannot provide a numeric download/install sum or exact peak disk figure for this plan.

## Exact dependency closure (199 formulae)

This is the unique formula set returned by `HOMEBREW_NO_AUTO_UPDATE=1 brew deps osrf/simulation/gz-harmonic`, including formulas supplied by the OSRF tap:

```text
abseil
ampl-asl
aom
apache-arrow
assimp
aws-c-auth
aws-c-cal
aws-c-common
aws-c-compression
aws-c-event-stream
aws-c-http
aws-c-io
aws-c-mqtt
aws-c-s3
aws-c-sdkutils
aws-checksums
aws-crt-cpp
aws-sdk-cpp
boost
brotli
bullet
c-ares
c-blosc
ca-certificates
cairo
cfitsio
cgal
cmake
console_bridge
cppzmq
dartsim
dav1d
doxygen
eigen
epsilon
fcl
ffmpeg
flann
fmt
fontconfig
freeimage
freetype
freexl
gcc
gdal
geos
gettext
gflags
giflib
glib
gmp
gnupg
gnutls
google-benchmark
gpgme
gpgmepp
graphite2
grpc
gts
gz-cmake3
gz-common5
gz-fuel-tools9
gz-gui8
gz-launch7
gz-math7
gz-msgs10
gz-physics7
gz-plugin2
gz-rendering8
gz-sensors8
gz-sim8
gz-tools2
gz-transport13
gz-utils2
harfbuzz
hdf5
highway
hwloc
icu4c@78
imath
ipopt
isl
jasper
jpeg-turbo
jpeg-xl
json-c
jsoncpp
krb5
lame
libaec
libarchive
libassuan
libb2
libccd
libde265
libdeflate
libgcrypt
libgeotiff
libgpg-error
libheif
libidn2
libkml
libksba
liblerc
libmpc
libomp
libpng
libpq
librttopo
libsodium
libspatialite
libtasn1
libtiff
libtool
libunistring
libusb
libvmaf
libvpx
libx11
libxau
libxcb
libxdmcp
libxext
libxml2
libxrender
libyaml
libzip
libzzip
little-cms2
llvm@22
lz4
lzo
m4
md4c
minizip
mpdecimal
mpfr
mpg123
netcdf
netpbm
nettle
nlopt
npth
nspr
nss
numpy
octomap
ode
ogre1.9
ogre2.3-with-freeimage
open-scene-graph
openblas
openexr
openjpeg
openjph
openssl@3
opus
ossp-uuid
p11-kit
pcre2
pinentry
pixman
pkgconf
poppler
popt
proj
protobuf
python@3.14
qhull
qt@5
rapidjson
re2
readline
ruby
s2n
sdformat14
sdl2-compat
sdl3
sfcgal
snappy
spdlog
sqlite
svt-av1
tbb
thrift
tinyxml2
unixodbc
urdfdom
urdfdom_headers
uriparser
utf8proc
webp
x264
x265
xerces-c
xorgproto
xz
zeromq
zstd
```

### Not currently installed (183 formulae)

The following closure members do not appear in `brew list --formula`:

```text
ampl-asl
aom
apache-arrow
assimp
aws-c-auth
aws-c-cal
aws-c-common
aws-c-compression
aws-c-event-stream
aws-c-http
aws-c-io
aws-c-mqtt
aws-c-s3
aws-c-sdkutils
aws-checksums
aws-crt-cpp
aws-sdk-cpp
boost
bullet
c-blosc
cairo
cfitsio
cgal
cmake
console_bridge
cppzmq
dartsim
dav1d
doxygen
eigen
epsilon
fcl
ffmpeg
flann
fontconfig
freeimage
freetype
freexl
gcc
gdal
geos
gettext
gflags
giflib
glib
gmp
gnupg
gnutls
google-benchmark
gpgme
gpgmepp
graphite2
grpc
gts
gz-cmake3
gz-common5
gz-fuel-tools9
gz-gui8
gz-launch7
gz-math7
gz-msgs10
gz-physics7
gz-plugin2
gz-rendering8
gz-sensors8
gz-sim8
gz-tools2
gz-transport13
gz-utils2
harfbuzz
hdf5
hwloc
imath
ipopt
isl
jasper
jpeg-turbo
jpeg-xl
json-c
jsoncpp
krb5
lame
libaec
libarchive
libassuan
libb2
libccd
libde265
libdeflate
libgcrypt
libgeotiff
libgpg-error
libheif
libidn2
libkml
libksba
liblerc
libmpc
libomp
libpng
libpq
librttopo
libsodium
libspatialite
libtasn1
libtiff
libtool
libunistring
libusb
libvmaf
libvpx
libx11
libxau
libxcb
libxdmcp
libxext
libxml2
libxrender
libyaml
libzip
libzzip
little-cms2
llvm@22
lzo
m4
md4c
minizip
mpfr
mpg123
netcdf
netpbm
nettle
nlopt
npth
nspr
nss
numpy
octomap
ode
ogre1.9
ogre2.3-with-freeimage
open-scene-graph
openblas
openexr
openjpeg
openjph
opus
ossp-uuid
p11-kit
pinentry
pixman
pkgconf
poppler
popt
proj
protobuf
qhull
qt@5
rapidjson
re2
ruby
s2n
sdformat14
sdl2-compat
sdl3
sfcgal
snappy
spdlog
svt-av1
tbb
thrift
tinyxml2
unixodbc
urdfdom
urdfdom_headers
uriparser
utf8proc
webp
x264
x265
xerces-c
xorgproto
zeromq
```

The 16 installed closure members are: `abseil`, `brotli`, `c-ares`, `ca-certificates`, `fmt`, `highway`, `icu4c@78`, `lz4`, `mpdecimal`, `openssl@3`, `pcre2`, `python@3.14`, `readline`, `sqlite`, `xz`, and `zstd`.

## Bottles, source builds, and major dependency groups

Current platform bottle tag is `arm64_tahoe` for this ARM64 macOS 26.3 system. Of the 183 missing formulas, **160** have an `arm64_tahoe` bottle, **5** have a universal `all` bottle, and **18** have only an `arm64_sequoia` bottle. The installed Homebrew 7.0.7 tag resolver matches the current tag or the universal `all` tag; it does not select an older macOS tag. Thus those 18 Sequoia-only formulas are expected to build from source on this host. The root `gz-harmonic` formula also has no bottle. This count follows current local metadata; it is not a claim that every formula build will succeed.

The 18 missing formulas without a Tahoe or universal bottle are:

```text
gz-cmake3
gz-common5
gz-fuel-tools9
gz-gui8
gz-launch7
gz-math7
gz-msgs10
gz-physics7
gz-plugin2
gz-rendering8
gz-sensors8
gz-sim8
gz-tools2
gz-transport13
gz-utils2
ogre1.9
ogre2.3-with-freeimage
sdformat14
```

| Group | Required closure members | Bottle/build status and expected work |
|---|---|---|
| Gazebo core and simulator | `gz-cmake3`, `gz-common5`, `gz-fuel-tools9`, `gz-gui8`, `gz-launch7`, `gz-math7`, `gz-msgs10`, `gz-physics7`, `gz-plugin2`, `gz-rendering8`, `gz-sensors8`, `gz-sim8`, `gz-tools2`, `gz-transport13`, `gz-utils2`, `sdformat14` | These OSRF formulae are Sequoia-only bottles in current metadata, so expected source builds. Several are C++ libraries; `gz-gui8`, `gz-rendering8`, `gz-sensors8`, and `gz-sim8` are among the more compilation-intensive source stages. |
| Rendering engines | `ogre1.9`, `ogre2.3-with-freeimage`, `open-scene-graph`, `assimp`, `bullet`, `fcl`, `dartsim`, `cgal`, `eigen` | OGRE 1.9 and OGRE 2.3 are Sequoia-only and expected to build from source. OpenSceneGraph, Assimp, Bullet, FCL, DART, and the current Tahoe-tagged dependencies are bottled; CGAL/Eigen are universal bottles. OGRE source compilation is a likely high-RAM stage. |
| GUI toolkit | `qt@5` and its Qt/X11 dependencies | Tahoe bottles are available for this dependency group. It is a large binary payload but is not expected to be a Qt source build under normal bottle use. |
| Toolchains and numerical libraries | `llvm@22`, `gcc`, `boost`, `cmake`, `cgal`, `eigen`, `openblas`, `gmp`, `mpfr` | These are present in the dependency closure. LLVM, GCC, Boost, and CMake have Tahoe bottles in current metadata; they are not expected to compile from source for this plan. |
| Media and image stack | `ffmpeg`, `aom`, `dav1d`, `libvpx`, `x264`, `x265`, `openexr`, `jpeg-xl`, `freeimage`, `ogre2.3-with-freeimage` | Required through rendering/common dependencies. Most have Tahoe bottles; the OGRE 2.3 tap formula is Sequoia-only and expected to build from source. |
| Geospatial and data | `gdal`, `proj`, `geos`, `libgeotiff`, `libspatialite`, `netcdf`, `hdf5`, `apache-arrow`, `aws-sdk-cpp` | Required in the closure. Current Tahoe bottles are listed for these; no source build is expected when Homebrew pours those bottles. |
| Other large C/C++ libraries | `grpc`, `protobuf`, `thrift`, `xerces-c`, `nss`, `numpy`, `poppler`, `libpq` | Required transitively. Tahoe bottles are listed in current metadata. |

The specific packages asked about—LLVM, GCC, Qt, both OGRE formulae, OpenSceneGraph, Boost, FFmpeg, GDAL, and PROJ—are all in the closure. Their mere presence in the graph does not mean each will be compiled: the current metadata lists Tahoe bottles for all of these except the two OGRE tap formulae, which have Sequoia-only bottles and are expected source builds.

### Size metadata and historical evidence

Homebrew metadata does not provide the requested source/download or installed-size values for this closure. It is not possible to rank current formulae precisely by those sizes from `brew info` metadata. The group table above identifies the likely largest build complexity and binary payloads, not measured sizes.

**Historical evidence only, not used as a Harmonic size estimate:** the previous failed Jetty attempt staged 5.3 GiB across 194 temporary formula directories. Its recorded larger staged directories included `llvm@22` (about 1.5 GiB), `aws-sdk-cpp` (about 803 MiB), `gcc` (about 481 MiB), `boost` (about 378 MiB), and `open-scene-graph` (about 279 MiB). Those were Jetty transaction staging sizes, not installed sizes; versions, closure, and build outcome differ, so they must not be extrapolated to Harmonic.

## Disk estimate

There is no formula metadata from which to calculate a defensible exact peak. For planning only, reserve **about 30 GiB of free disk** for bottle downloads, installed formulae, temporary bottle staging, and source build directories. This is an engineering allowance, **not** a Homebrew-reported bound or a guarantee. With 41 GiB currently free, the estimated margin is about 11 GiB. Keep monitoring free space during any future install and retain that margin; the exact peak remains uncertain without archive and installed-size data.

## RAM and build parallelism

The root formula and 18 Sequoia-only dependencies are the expected source builds; the very large compiler/toolchain dependencies (LLVM and GCC) have Tahoe bottles. Likely high-memory compile phases are OGRE 1.9/2.3 and Gazebo rendering, GUI, sensors, and simulator C++ sources. Actual peak RAM is not reported by formula metadata. On an 8 GB machine, compiling these with unrestricted per-build parallelism risks memory pressure and macOS swap use.

Homebrew installs formula dependencies in dependency order, one formula installer at a time (the local Homebrew 7.0.7 installer loops over dependencies sequentially). A single formula's `make`-based build can still run parallel jobs. Homebrew's documented default for `HOMEBREW_MAKE_JOBS` is the number of available CPU cores. It can be constrained for one command, without changing configuration, by setting `HOMEBREW_MAKE_JOBS=2` (or `1`) in that command's environment. The Homebrew manpage also documents `HOMEBREW_DOWNLOAD_CONCURRENCY`; default `auto` is twice available CPU cores, and `1` makes downloads serial. These are separate controls; limiting make jobs does not itself serialize downloads.

References: [Homebrew manpage: build and download parallelism](https://docs.brew.sh/Manpage), [Homebrew bottle documentation](https://github.com/Homebrew/brew/blob/main/docs/Bottles.md).

## Feasibility assessment

A 41 GiB free-space baseline is above the approximately 30 GiB planning allowance, but only by an estimated 11 GiB; because exact package sizes are missing, this is not a guaranteed disk bound. The ARM64 host has Tahoe bottles for 165 of the 183 missing dependencies, and only 18 dependencies plus the top-level collection formula are expected to build from source. This makes disk capacity plausible with active space monitoring. The 8 GB RAM limit makes constrained build parallelism prudent for OGRE and Gazebo C++ compilation.

**Factual classifications:**

- **Feasible without special measures:** No. The 8 GB RAM limit makes unrestricted parallel compilation a material risk, and the disk estimate is not a guaranteed upper bound.
- **Feasible with constrained build parallelism / disk management:** Yes, conditionally. Use a low `HOMEBREW_MAKE_JOBS` value and monitor available disk against the approximately 30 GiB planning allowance.
- **Impractical on this machine:** No, based on current formula and bottle metadata; 165 missing dependencies have current-platform or universal bottles, while 18 are expected to build from source. Exact peak disk use and source-build success remain uncertain.
