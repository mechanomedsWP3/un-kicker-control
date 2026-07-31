import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CALIBRATION_PATH = Path.home() / ".un_kicker_control" / "calibration.json"

# Hardware limit of the device's amplitude setpoint (see NanoKicker.set_amplitude).
# Amplitude is peak-to-peak and the device is supplied at 24V, so the achievable
# peak-to-peak swing tops out at 12V, not 24V.
AMPLITUDE_MAX = 12.0


class CalibrationStore:
    """
    Manually-measured (frequency -> gain) calibration points per device.

    A piezo actuator's capacitance attenuates the commanded drive voltage by an
    amount that depends on frequency, so the voltage the device tells the
    NanoKicker to output is not the voltage actually appearing across the
    actuator. Each calibration point pairs a commanded amplitude with the
    voltage a user measured across the actuator (with an oscilloscope) at a
    given frequency; the ratio measured/commanded is treated as that
    frequency's gain, linearly interpolated between measured frequencies.
    """

    def __init__(self, path=None):
        self.path = Path(path) if path else DEFAULT_CALIBRATION_PATH
        self._data = self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not read calibration file %s: %s", self.path, e)
        return {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def points(self, device_id):
        """Return the calibration points for a device, sorted by frequency."""
        return sorted(self._data.get(str(device_id), []), key=lambda p: p["frequency"])

    def add_point(self, device_id, frequency, commanded_amplitude, measured_voltage):
        """Always appends a new point, even at a frequency already recorded --
        re-measuring the same frequency is a legitimate second data point,
        not a correction, so it's up to the user to remove a stale one."""
        if commanded_amplitude <= 0:
            raise ValueError("Commanded amplitude must be positive.")
        key = str(device_id)
        points = self._data.setdefault(key, [])
        points.append(
            {
                "frequency": frequency,
                "commanded_amplitude": commanded_amplitude,
                "measured_voltage": measured_voltage,
                "gain": measured_voltage / commanded_amplitude,
            }
        )
        self._save()

    def remove_point(self, device_id, index):
        """Remove the point at `index` in the frequency-sorted list returned
        by points() -- i.e. the row index as shown in the calibration table.
        Removes by identity, not by frequency, since frequencies need not
        be unique.
        """
        key = str(device_id)
        points = self._data.get(key, [])
        sorted_points = self.points(device_id)
        if 0 <= index < len(sorted_points):
            target = sorted_points[index]
            points[:] = [p for p in points if p is not target]
            self._save()

    def gain_at(self, device_id, frequency):
        """Interpolate the calibrated gain at the given frequency.

        Returns None if this device has no calibration points. Frequencies
        outside the calibrated range fall back to the nearest point's gain.
        """
        points = self.points(device_id)
        if not points:
            return None
        if frequency <= points[0]["frequency"]:
            return points[0]["gain"]
        if frequency >= points[-1]["frequency"]:
            return points[-1]["gain"]

        for lower, upper in zip(points, points[1:]):
            if lower["frequency"] <= frequency <= upper["frequency"]:
                span = upper["frequency"] - lower["frequency"]
                if span == 0:
                    return lower["gain"]
                t = (frequency - lower["frequency"]) / span
                return lower["gain"] + t * (upper["gain"] - lower["gain"])
        return points[-1]["gain"]

    def commanded_amplitude_for(self, device_id, frequency, desired_voltage):
        """Return the amplitude to command so the actual voltage across the
        actuator matches desired_voltage at the given frequency, or None if
        this device has no calibration data yet."""
        gain = self.gain_at(device_id, frequency)
        if not gain:
            return None
        return desired_voltage / gain
