from pathlib import Path

import yaml

from task3_vision.homography import project, solve_homography


ROOT = Path(__file__).resolve().parents[1]


def load_config():
    with (ROOT / "config" / "vision_config.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_task1_detection_topic_and_two_classes():
    config = load_config()
    assert config["camera"]["detections_topic"] == "/detections/json"
    assert config["classes"]["charger"]["region"] == "A"
    assert config["classes"]["staple_shell"]["region"] == "B"
    assert config["classes"]["by_id"][0] == "A"
    assert config["classes"]["by_id"][1] == "B"


def test_tight_grip_and_safe_pose_within_limits():
    config = load_config()
    assert config["robot"]["gripper_close_value"] == 0
    safe = config["geometry"]["rotation_safe_joints_deg"]
    lower = config["limits"]["lower"]
    upper = config["limits"]["upper"]
    assert len(safe) == len(lower) == len(upper) == 6
    assert all(low <= value <= high for value, low, high in zip(safe, lower, upper))


def test_homography_maps_pixels_to_table_plane():
    pairs = [
        ((0.0, 0.0), (0.10, -0.10)),
        ((640.0, 0.0), (0.30, -0.10)),
        ((640.0, 480.0), (0.30, 0.10)),
        ((0.0, 480.0), (0.10, 0.10)),
        ((320.0, 240.0), (0.20, 0.00)),
    ]
    matrix = solve_homography(pairs, (640, 480))
    mapped = project(matrix, 320.0, 240.0)
    assert mapped is not None
    assert abs(mapped[0] - 0.20) < 1e-6
    assert abs(mapped[1]) < 1e-6
