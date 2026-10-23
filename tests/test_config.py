import copy

from formcoach.core.config import load_config, merged, save_config


def test_save_keeps_comments_and_values(tmp_path):
    cfg = load_config()
    path = tmp_path / "ex.yaml"
    path.write_text(open("config/exercises.yaml").read())
    cfg2 = copy.deepcopy(cfg)
    cfg2["push_up"]["thresholds"]["depth_max_elbow"] = 97
    cfg2["squat"]["counter"]["start"] = 150.5
    save_config(cfg2, path)
    text = path.read_text()
    assert "# FormCoach exercise configuration" in text
    assert "depth_max_elbow: 97" in text and "# ... or the elbow" in text
    assert load_config(path) == cfg2


def test_save_new_keys_falls_back_to_full_dump(tmp_path):
    path = tmp_path / "ex.yaml"
    path.write_text(open("config/exercises.yaml").read())
    cfg = load_config(path)
    cfg["general"]["new_option"] = 1
    save_config(cfg, path)
    assert load_config(path) == cfg


def test_merged_is_deep_and_non_destructive():
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    out = merged(base, {"a": {"b": 10}})
    assert out == {"a": {"b": 10, "c": 2}, "d": 3}
    assert base["a"]["b"] == 1
