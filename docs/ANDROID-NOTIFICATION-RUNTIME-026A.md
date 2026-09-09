# PC-local Android notification runtime — 026A

Status: **PLAY NETWORK REPAIRED / LIVE VENDOR CAPTURE NOT CONNECTED**. Checked
on atlas-desktop, 2026-09-07 UTC. Later qualification updates below supersede
the initial no-live-pass statement without removing that historical evidence.

## Installed and observed

- Official Waydroid APT package 1.6.2; Weston 13.0.0; ADB 34.0.4-debian
  (protocol executable version 1.0.41).
- Official verified GAPPS system image 20260403 and MAINLINE vendor 20260428.
- Android 13 x86_64 booted under a headless compositor with both
  `sys.boot_completed=1` and `dev.bootcomplete=1`; Play Store package exists.
- Data and images are on native PC storage under `/var/lib/waydroid`, not the
  shared laptop folder. No household vault is mounted into Android.
- The official Tapo and Wansview applications are installed from Google Play,
  and the owner completed both vendor sign-ins directly. Credentials, Android
  IDs, camera media and account data were not extracted into ANIMA.
- Real Tapo DL110 lock and unlock notifications were observed privately. Their
  bounded package/resource/state format is qualified; raw mode-0600 calibration
  records were removed after qualification.
- A Wansview motion trigger was attempted outside the owner's configured
  00:00-05:00 notification schedule. No Android notification was emitted, so
  Wansview remains disabled and capture-only until one scheduled or temporarily
  enabled real notification is observed.

The Android session/compositor and container are currently running for owner
setup. The existing SENTRY voice/UI/state services, ANIMA and HA remain running.

## Play network repair

The initial Android session had `eth0` but no IPv4 lease, route or framework
DNS. The installed Waydroid 1.6.2 network helper preferred `iptables-legacy`
while this host's UFW and Docker rules use the nft backend. Its DHCP, DNS,
forward and masquerade rules therefore did not protect the traffic from the
active UFW policy. The repair:

- enables Waydroid's nft rules in the installed network helper;
- gives the Waydroid nft input/forward chains an earlier hook priority;
- adds persistent, interface/subnet-bounded UFW rules for DHCP, host DNS and
  forwarded egress;
- retains `suspend_action = none` and prevents the installed 1.6.2 hardware
  manager from treating that value as `freeze`.

After a complete container/session restart, dnsmasq issued
`192.168.240.112`, Android installed its default route and framework DNS, a
hostname ping to `play.google.com` passed, and Android curl received HTTP 302
from `https://play.google.com/store`. The Play Store package was launched to its
unauthenticated main activity. Google account sign-in and vendor application
installation remain owner actions and are not claimed complete.

Package originals are retained at
`/usr/lib/waydroid/data/scripts/waydroid-net.sh.anima-backup` and
`/usr/lib/waydroid/tools/services/hardware_manager.py.anima-backup`. Package
updates can replace the installed corrections and therefore require a network
recheck.

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

The repository now includes an owner-user installer for persistent private-bus,
relay, compositor and Waydroid-session services. The installed user units are
enabled and currently active. Stop the user slice with:

```sh
systemctl --user stop anima-android-session anima-vendor-notification-relay \
  anima-android-bus anima-android-compositor
sudo systemctl stop waydroid-container
```

## Remaining source connection

Installed Waydroid's `notification_manager.py` forwards notifications to
`org.freedesktop.Notifications.Notify`, with the application package in the
`desktop-entry` hint prefixed by `waydroid.`. The ANIMA-owned private-bus relay
now owns that interface on an isolated D-Bus session, rejects every package but
the exact Tapo/Wansview identifiers before reading text, and emits only typed,
minimized reports to the loopback ANIMA receiver. It never forwards images,
actions, links or raw notification text.

The forwarding API does not provide Android notification post time, channel ID,
group-summary flag or camera capture time. Missing fields must remain unknown;
Linux receipt time is not camera event time. Images/URIs and unrelated packages
must be ignored before any text extraction. A real Wansview sample is required
to qualify camera-alias/motion extraction; structured ANIMA relay reports do not
prove that vendor parser. No image/video feed is in scope. Tapo and Wansview use
separately derived receiver credentials even though one host relay serves both.

## Live vendor-format qualification update — 2026-09-07

The official Tapo package emitted real Front Door locked and unlocked notices;
the official Wansview package emitted two real `Motion alert` notices with the
body `New motion alert from Garage`. The private relay now matches only those
qualified event phrases and the commissioned resource aliases. Empty and other
same-app notices remain rejected. Raw mode-0600 calibration content was removed,
the volatile capture file is empty, and further capture is disabled.

Both package-scoped ANIMA receiver registrations are enabled and producer-
qualified. Tapo reached the Journal, exact Attention path, and resident SENTRY
claim during physical use. Wansview still needs one new motion after enablement
to prove the complete receiver-to-SENTRY path; the two format samples arrived
while Wansview was capture-only. The owner's normal Wansview schedule remains
00:00-05:00 and should be restored after any temporary daytime qualification.
Headless cold-boot push recovery remains a separate operational check.

References: [Waydroid desktop installation](https://docs.waydro.id/usage/install-on-desktops)
and the installed Waydroid 1.6.2 notification service source. No APK mirror,
private vendor endpoint, scraping, or Google certification bypass was used.
