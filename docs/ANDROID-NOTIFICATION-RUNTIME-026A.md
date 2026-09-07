# PC-local Android notification runtime — 026A

Status: **PREPARED / LIVE VENDOR CAPTURE NOT CONNECTED**. Checked on
atlas-desktop, 2026-09-07 UTC. This is not a Wansview or Tapo live pass.

## Installed and observed

- Official Waydroid APT package 1.6.2; Weston 13.0.0; ADB 34.0.4-debian
  (protocol executable version 1.0.41).
- Official verified GAPPS system image 20260403 and MAINLINE vendor 20260428.
- Android 13 x86_64 booted under a headless compositor with both
  `sys.boot_completed=1` and `dev.bootcomplete=1`; Play Store package exists.
- Data and images are on native PC storage under `/var/lib/waydroid`, not the
  shared laptop folder. No household vault is mounted into Android.
- No Tapo/Wansview application, vendor account, Google sign-in or Google device
  certification was configured. No account credentials or Android IDs were
  extracted. No real vendor notification was captured.

The temporary Android session/compositor and container are now **stopped**;
container autostart is disabled. Images and packages remain installed for setup.
The existing SENTRY voice/UI/state services, ANIMA and HA remain running.

## Notification-only preparation and negative evidence

The first stock Waydroid startup attempted to broaden host video/render device
permissions and expose camera nodes. It was stopped. Video/render nodes were
restored to 0660 and the system dma heap to 0600. This initial failure is not a
successful privacy test.

The subsequent container-service override is installed at
`/etc/systemd/system/waydroid-container.service.d/anima-notifications.conf`:

```ini
[Service]
InaccessiblePaths=-/dev/video0 -/dev/video1 -/dev/v4l -/dev/snd
ReadOnlyPaths=-/dev/dri -/dev/dma_heap
```

On the corrected boot, Android's camera nodes were inaccessible 0,0 devices;
host video/render permissions remained 0660. The session uses a dummy regular
file in place of the PulseAudio socket, not a microphone/audio server. The
system Python lacks pyclip, so Waydroid's clipboard manager does not run.
These checks cover the present workstation device inventory; new camera/audio
hardware requires revalidation. This is not a general Android sandbox claim.

## Reproduce the bounded boot

Recheck the override and current device inventory before starting. The runtime
directory below must be owner-private. Create its empty regular `native` file
using the ordinary file-edit mechanism; never point it at the actual PulseAudio
socket. It lives under `/run` and must be recreated after logout/reboot.

```sh
install -d -m 700 /run/user/1000/anima-android-no-audio
sudo systemctl start waydroid-container
systemd-run --user --unit=anima-android-compositor --property=UMask=0077 \
  /usr/bin/weston --backend=headless --renderer=pixman \
  --socket=anima-android-wayland --idle-time=0 --no-config
systemd-run --user --unit=anima-android-session --property=UMask=0077 \
  --setenv=WAYLAND_DISPLAY=anima-android-wayland \
  --setenv=PULSE_RUNTIME_PATH=/run/user/1000/anima-android-no-audio \
  /usr/bin/dbus-run-session -- /usr/bin/waydroid session start
```

The units are temporary qualification units, not unattended startup services.
Stop with:

```sh
systemctl --user stop anima-android-session anima-android-compositor
sudo systemctl stop waydroid-container
```

## Remaining source connection

Installed Waydroid's `notification_manager.py` forwards notifications to
`org.freedesktop.Notifications.Notify`, with the application package in the
`desktop-entry` hint prefixed by `waydroid.`. A dedicated service on the private
session bus can consume this without intercepting the desktop notification bus.
**That private-bus collector is not implemented or running yet.** No sink is
registered, so the present session does not forward notifications.

The forwarding API does not provide Android notification post time, channel ID,
group-summary flag or camera capture time. Missing fields must remain unknown;
Linux receipt time is not camera event time. Images/URIs and unrelated packages
must be ignored before any text extraction. A real Wansview sample is required
to qualify camera-alias/motion extraction; structured ANIMA relay reports do not
prove that vendor parser. No image/video feed is in scope.

Operator next step: confirm/add the devices in the official apps and complete
necessary account sign-in directly. Do not send passwords or setup codes to the
assistant. Then qualify one actual motion notification, reconnection and loss
semantics before enabling a producer or SENTRY wake. Headless unattended push,
cold boot and vendor session recovery remain unqualified.

References: [Waydroid desktop installation](https://docs.waydro.id/usage/install-on-desktops)
and the installed Waydroid 1.6.2 notification service source. No APK mirror,
private vendor endpoint, scraping, or Google certification bypass was used.
