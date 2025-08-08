# video.py/Open GoPro, Version 2.0 (C) Copyright 2021 GoPro, Inc. (http://gopro.com/OpenGoPro).
# Modified by Bjarne Cypers to also support dutch drivers
# This copyright was auto-generated on Wed, Sep  1, 2021  5:05:46 PM

# You need to be in 'Pair Device'-mode to make connection with the gopro

import argparse
import asyncio
import locale
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Signal, QObject

from open_gopro import WiredGoPro, WirelessGoPro
from open_gopro.models import constants, proto
from open_gopro.util import add_cli_args_and_parse

import open_gopro.network.wifi.adapters.wireless as gopro_wireless

from constants import NAME_APP


def bypass_locale_check():
    lang = locale.getlocale()[0]
    print(f"[Bypass] Taalcheck uitgeschakeld — huidige taal: {lang}")


gopro_wireless.ensure_us_english = bypass_locale_check

# Force english driver:
os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"
locale.setlocale(locale.LC_ALL, "en_US.UTF-8")


class GoPro(QObject):
    started = Signal()
    stopped = Signal()
    error = Signal(str)
    connected = Signal()
    download_progress = Signal(str)
    time_trial_start = Signal(float)
    request_trial_start = Signal()

    def __init__(self, parent, part_folder, id_part):
        super().__init__(parent)
        self.args = self.parse_arguments(part_folder, id_part)
        self.gopro = None
        self.media_set_before = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.time_start_recording = None
        self.request_trial_start.connect(self.start_trial_timer)

    def start_recording(self):
        """Start the recording process - NON-ASYNC method"""
        try:
            # Submit to thread executor and return immediately
            future = self._executor.submit(self._start_recording_sync)
            # Don't wait for result - let it run in background
            # The signals will notify when done

        except Exception as e:
            self.error.emit(f"Error starting recording thread: {str(e)}")

    def stop_recording(self):
        """Stop recording - NON-ASYNC method"""
        try:
            # Submit to thread executor and return immediately
            future = self._executor.submit(self._stop_recording_sync)
            # Don't wait for result - let it run in background

        except Exception as e:
            self.error.emit(f"Error stopping recording thread: {str(e)}")

    def _start_recording_sync(self):
        """Synchronous wrapper for start recording - runs in thread"""
        try:
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # Connect if needed
            if self.gopro is None:
                self.loop.run_until_complete(self._connect_gopro_async())

            # Start recording
            if self.gopro is not None:
                self.loop.run_until_complete(self._start_recording_async())
                # Emit signal - this is thread-safe in Qt
                self.started.emit()
            else:
                self.error.emit("Failed to connect to GoPro")

        except Exception as e:
            self.error.emit(f"Error in start recording: {str(e)}")

    def _stop_recording_sync(self):
        """Synchronous wrapper for stop recording - runs in thread"""
        try:
            try:
                if self.gopro is not None:
                    self.loop.run_until_complete(self._stop_recording_async())
                    # Emit signal - this is thread-safe in Qt
                    self.stopped.emit()
                else:
                    self.error.emit("No GoPro connection to stop")

            finally:
                self.close_loop()

        except Exception as e:
            self.error.emit(f"Error in stop recording: {str(e)}")

    async def _connect_gopro_async(self):
        """Connect to the GoPro device"""
        try:
            print("Connecting to GoPro...")

            if self.args.wired:
                self.gopro = WiredGoPro(self.args.identifier)
            else:
                file_directory = (os.path.dirname(os.path.abspath(__file__)))
                if getattr(sys, 'frozen', False):
                    # Running as packaged executable
                    log_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', NAME_APP, 'logs')
                else:
                    # Running from source (PyCharm/development)
                    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

                self.gopro = WirelessGoPro(
                    self.args.identifier,
                    host_wifi_interface=self.args.wifi_interface,
                    cohn_db=Path(log_dir)/'cohn_db.json'
                )

            await self.gopro.open()
            print("Connected to GoPro successfully")
            self.connected.emit()  # Thread-safe signal emission

        except Exception as e:
            error_msg = f"Failed to connect to GoPro: {str(e)}"
            print(error_msg)
            self.gopro = None
            raise Exception(error_msg)

    async def _start_recording_async(self):
        """Start recording"""
        try:
            if not self.gopro:
                raise Exception("GoPro not connected")

            print("Setting up recording...")

            # Load video preset
            response = await self.gopro.http_command.load_preset_group(
                group=proto.EnumPresetGroup.PRESET_GROUP_ID_VIDEO
            )
            if not response.ok:
                raise Exception("Failed to load video preset")

            # Get the media set before recording
            media_response = await self.gopro.http_command.get_media_list()
            self.media_set_before = set(media_response.data.files)

            # Set keep alive
            await self.gopro.http_command.set_keep_alive(True)

            # Start recording
            print("Starting recording...")
            shutter_response = await self.gopro.http_command.set_shutter(
                shutter=constants.Toggle.ENABLE
            )

            if not shutter_response.ok:
                raise Exception("Failed to start recording")

            self.time_start_recording = time.perf_counter()

            print("Recording started successfully!")

        except Exception as e:
            self.close_loop()
            error_msg = f"Error starting recording: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    async def _stop_recording_async(self):
        """Stop recording and download video"""
        try:
            if not self.gopro:
                raise Exception("GoPro not connected")

            print("Stopping recording...")

            # Stop recording
            shutter_response = await self.gopro.http_command.set_shutter(
                shutter=constants.Toggle.DISABLE
            )

            print('stopped recording')

            # Deactivate keep alive
            await self.gopro.http_command.set_keep_alive(False)

            if not shutter_response.ok:
                print("Warning: Failed to stop recording properly")

            # Wait a moment for the file to be processed
            await asyncio.sleep(2)

            print('done waiting')

            # Get the media set after recording
            media_response = await self.gopro.http_command.get_media_list()
            media_set_after = set(media_response.data.files)

            # Find the new video file
            new_files = media_set_after.difference(self.media_set_before)

            print('found new file')

            if new_files:
                video = new_files.pop()
                # Use signal for thread-safe communication
                self.download_progress.emit(f"Downloading {video.filename}...")

                counter = 0
                video_file = Path(self.args.output)
                while video_file.with_suffix('.mp4').exists():
                    counter += 1
                    video_file = video_file.with_name(f"{self.args.output.stem} ({counter})")

                await self.gopro.http_command.download_file(
                    camera_file=video.filename,
                    local_file=video_file.with_suffix('.mp4')
                )
                self.download_progress.emit(f"Video saved to {video_file.with_suffix('.mp4')}")
            else:
                print("No new video files found")

            # Close the connection
            if self.gopro:
                await self.gopro.close()
                self.gopro = None

            print("Recording stopped and downloaded successfully")

        except Exception as e:
            error_msg = f"Error stopping recording: {str(e)}"
            print(error_msg)
            # Still try to close the connection
            if self.gopro:
                try:
                    await self.gopro.close()
                except:
                    pass
                self.gopro = None
            raise Exception(error_msg)

    def cleanup(self):
        """Clean up resources"""
        self._executor.shutdown(wait=True)

    def parse_arguments(self, part_folder, id) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Connect to a GoPro camera, take a video, then download it.")
        parser.add_argument("-r", "--record_time", type=float, help="How long to record for", default=10.0)
        Path(part_folder).mkdir(parents=True, exist_ok=True)
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            help="Where to write the video to (not including file type). If not set, write to 'video'",
            default=Path(part_folder)/id,
        )
        parser.add_argument(
            "--wired",
            action="store_true",
            help="Set to use wired (USB) instead of wireless (BLE / WIFI) interface",
        )
        return add_cli_args_and_parse(parser)

    def start_trial_timer(self):
        if self.time_start_recording:
            start_of_trial = time.perf_counter() - self.time_start_recording
            self.time_trial_start.emit(start_of_trial)

    def close_loop(self):
        if self.loop is not None and not self.loop.is_closed():
            if self.loop.is_running():
                self.loop.stop()

            pending = asyncio.all_tasks(self.loop)
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            self.loop.close()

