# Smart Shopping Cart

## Jetson Nano USB camera

The vision scripts use V4L2 on Linux/Jetson and automatically try both camera
indices `0` and `1`. The detector now uses 640x360 MJPEG capture, `yolov8n.pt`,
320-pixel CPU inference, and 5 inferences per second to avoid exhausting the
Nano's memory and CPU. Increase these only after the basic pipeline is stable.

### Step-by-step camera diagnosis

Before starting YOLO, probe the camera without opening a GUI or loading
PyTorch:

```bash
timeout 15s python3 camera_probe.py --device /dev/video0 --width 640 --height 360
```

If that reports no device or fails to open, repeat with `/dev/video1`:

```bash
timeout 15s python3 camera_probe.py --device /dev/video1
```

The probe requests MJPEG, which is supported by this camera and avoids the
YUYV mode that timed out on the Nano. It must report ten successful frames
before moving on to YOLO. If it
times out or freezes, stop there and check the printed `/dev/video*` list,
camera permissions, USB power, and the Jetson power supply. The next step
depends on this probe result.

Install the Python dependencies using the versions compatible with the
JetPack image. In particular, install NVIDIA's JetPack-compatible PyTorch
build before installing Ultralytics; do not replace it with a generic desktop
PyTorch wheel.

Run object detection with:

```bash
python3 detect_objects.py --camera 0 --model yolov8n.pt
```

The detector displays the adjustable cart zone in the camera window. Drag any
of the four green corner handles to position it over the cart, press `s` to
save the corners to `config/zone_config.json`, or press `r` to reset them.
This uses OpenCV mouse callbacks and the V4L2 camera backend on Linux/Jetson;
no Windows-specific capture code is required. Use a different configuration
file with `--zone-config /path/to/zone.json` when needed.

To verify the USB camera without loading YOLO:

```bash
python3 detect_objects.py --camera 0 --camera-only
```

Once camera-only mode is stable, test YOLO on CPU:

```bash
python3 detect_objects.py --camera 0 --device cpu
```

Run the cart tracker with:

```bash
python3 main_cart.py --camera 0 --model yolov8n.pt
```

Use `--camera 1` if the camera is exposed as `/dev/video1`. Press `c` while a
window is open to switch between indices. If neither index opens, verify the
camera with `ls -l /dev/video*` and make sure the user is in the `video` group.

## React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
