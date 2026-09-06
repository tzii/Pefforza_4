"""Camera-controller regressions with fake frames, no windows or devices."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

import main as live_ar
from pefforza.cli import play_physical
from pefforza.constants import ROWS
from pefforza.rules import empty_board, next_open_row, swap_perspective
from pefforza.vision import diagnose


def _board(moves):
    board = empty_board()
    for index, col in enumerate(moves):
        board[next_open_row(board, col), col] = 1 + index % 2
    return board


def _camera_harness(monkeypatch, module, boards, *, opened=True):
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    camera = Mock()
    camera.isOpened.return_value = opened
    camera.read.side_effect = [(True, frame.copy()) for _ in boards] + [(False, None)]
    detector = Mock()
    detector.matrix = None
    detector.calibrate.return_value = True
    detector.physical_col.side_effect = lambda col: col
    detector.process_frame.side_effect = [(board, frame.copy()) for board in boards]
    monkeypatch.setattr(module, "BoardDetector", lambda: detector)
    monkeypatch.setattr(module.cv2, "VideoCapture", lambda _: camera)
    monkeypatch.setattr(module.cv2, "imshow", Mock())
    monkeypatch.setattr(module.cv2, "destroyAllWindows", Mock())
    monkeypatch.setattr(module.cv2, "waitKey", lambda _: ord(" "))
    monkeypatch.setattr(module.cv2, "putText", Mock())
    return camera, detector


@pytest.mark.parametrize("module", [live_ar, play_physical, diagnose])
def test_camera_open_failure_releases_resources(monkeypatch, module):
    camera, _ = _camera_harness(monkeypatch, module, [], opened=False)
    voice = Mock()
    if module is live_ar:
        monkeypatch.setattr(module, "PPO", None)
        monkeypatch.setattr(module, "VoiceEngine", lambda: voice)
    assert module.main([]) == 2
    camera.release.assert_called_once()
    if module is live_ar:
        voice.shutdown.assert_called_once()


def test_live_ar_caches_legal_move_for_unchanged_board(monkeypatch):
    board = _board([0, 0, 0, 0, 0, 0, 3])
    _, detector = _camera_harness(monkeypatch, live_ar, [board, board.copy()])
    model = Mock()
    model.predict.return_value = (0, None)
    monkeypatch.setattr(live_ar, "PPO", SimpleNamespace(load=lambda _: model))
    voice = Mock()
    monkeypatch.setattr(live_ar, "VoiceEngine", lambda: voice)
    assert live_ar.main(["--model", __file__]) == 0
    model.predict.assert_called_once()
    np.testing.assert_array_equal(model.predict.call_args.args[0], swap_perspective(board))
    drawn = [call.args[1] for call in detector.draw_move.call_args_list]
    assert len(drawn) == 2
    assert drawn[0] == drawn[1]
    assert board[0, drawn[0]] == 0
    voice.play_move_commentary.assert_called_once_with(drawn[0])


@pytest.mark.parametrize("kind", ["winner", "floating", "human_turn"])
def test_live_ar_never_recommends_for_unsafe_or_inactive_board(monkeypatch, kind):
    board = _board([0, 6, 0, 6, 0, 6, 0]) if kind == "winner" else empty_board()
    if kind == "floating":
        board[0, 0] = 1
    _, detector = _camera_harness(monkeypatch, live_ar, [board])
    model = Mock()
    model.predict.return_value = (3, None)
    monkeypatch.setattr(live_ar, "PPO", SimpleNamespace(load=lambda _: model))
    assert live_ar.main(["--no-voice", "--model", __file__]) == 0
    model.predict.assert_not_called()
    detector.draw_move.assert_not_called()


@pytest.mark.parametrize("failed_prediction", [False, True])
def test_live_ar_random_fallback_is_legal_and_stable(monkeypatch, failed_prediction):
    board = _board([0, 0, 0, 0, 0, 0, 3])
    _, detector = _camera_harness(monkeypatch, live_ar, [board, board.copy()])
    model = Mock()
    model.predict.side_effect = RuntimeError("model unavailable")
    ppo = SimpleNamespace(load=lambda _: model) if failed_prediction else None
    monkeypatch.setattr(live_ar, "PPO", ppo)
    assert live_ar.main(["--no-voice", "--model", __file__]) == 0
    drawn = [call.args[1] for call in detector.draw_move.call_args_list]
    assert len(drawn) == 2 and drawn[0] == drawn[1]
    assert board[0, drawn[0]] == 0


def test_live_ar_hides_rejected_read_without_reannouncing_last_good_move(monkeypatch):
    good = _board([3])
    bad = good.copy()
    bad[0, 0] = 2
    _, detector = _camera_harness(monkeypatch, live_ar, [good, bad, good.copy()])
    model = Mock()
    model.predict.return_value = (2, None)
    monkeypatch.setattr(live_ar, "PPO", SimpleNamespace(load=lambda _: model))
    voice = Mock()
    monkeypatch.setattr(live_ar, "VoiceEngine", lambda: voice)
    assert live_ar.main(["--model", __file__]) == 0
    model.predict.assert_called_once()
    voice.play_move_commentary.assert_called_once_with(2)
    assert detector.draw_move.call_count == 2


def test_live_ar_recommends_again_after_a_legal_round(monkeypatch):
    boards = [_board([3]), _board([3, 2, 3])]
    _, detector = _camera_harness(monkeypatch, live_ar, boards)
    model = Mock()
    model.predict.side_effect = [(2, None), (4, None)]
    monkeypatch.setattr(live_ar, "PPO", SimpleNamespace(load=lambda _: model))
    assert live_ar.main(["--no-voice", "--model", __file__]) == 0
    assert model.predict.call_count == 2
    assert [call.args[1] for call in detector.draw_move.call_args_list] == [2, 4]


def test_live_ar_reset_resynchronizes_rejected_history(monkeypatch):
    boards = [_board([3]), _board([4]), _board([4])]
    _, detector = _camera_harness(monkeypatch, live_ar, boards)
    keys = iter([ord(" "), ord("r"), ord("q")])
    monkeypatch.setattr(live_ar.cv2, "waitKey", lambda _: next(keys))
    model = Mock()
    model.predict.return_value = (2, None)
    monkeypatch.setattr(live_ar, "PPO", SimpleNamespace(load=lambda _: model))
    assert live_ar.main(["--no-voice", "--model", __file__]) == 0
    assert model.predict.call_count == 2
    assert detector.draw_move.call_count == 2


@pytest.mark.parametrize("missing", [False, True])
def test_physical_bad_read_clears_stale_arrow(monkeypatch, missing):
    good = _board([3])
    bad = good.copy()
    bad[0, 0] = 2
    _, detector = _camera_harness(monkeypatch, play_physical, [good, None if missing else bad])
    agent = Mock(return_value=2)
    monkeypatch.setattr(play_physical, "build_opponent", lambda *a, **kw: agent)
    assert play_physical.main(["--ai-color", "yellow"]) == 0
    agent.assert_called_once()
    detector.draw_move.assert_called_once()
    assert play_physical.cv2.imshow.call_count == 2


def test_physical_draw_announced_instead_of_waiting_for_opponent(monkeypatch, capsys):
    drawn = np.array(
        [[1, 1, 2, 2, 1, 1, 2], [2, 2, 1, 1, 2, 2, 1]] * (ROWS // 2),
        dtype=np.int8,
    )
    _camera_harness(monkeypatch, play_physical, [drawn])
    agent = Mock(return_value=2)
    monkeypatch.setattr(play_physical, "build_opponent", lambda *a, **kw: agent)
    assert play_physical.main(["--ai-color", "yellow"]) == 0
    agent.assert_not_called()
    output = capsys.readouterr().out
    assert "DRAW" in output
    assert "Opponent's turn" not in output


@pytest.mark.parametrize("save_result", [True, False, "exception"])
def test_diagnose_only_reports_successful_saves(monkeypatch, caplog, save_result):
    caplog.set_level(logging.INFO)
    board = empty_board()
    camera, detector = _camera_harness(monkeypatch, diagnose, [board, board.copy()])
    detector.width = 100
    detector.height = 100
    detector.cell_confidences.return_value = np.zeros_like(board, dtype=np.float32)
    keys = iter([ord("s"), ord("q")])
    monkeypatch.setattr(diagnose.cv2, "waitKey", lambda _: next(keys))
    save = Mock(return_value=save_result)
    if save_result == "exception":
        save.side_effect = diagnose.cv2.error("encoder unavailable")
    monkeypatch.setattr(diagnose.cv2, "imwrite", save)

    assert diagnose.main([]) == 0
    save.assert_called_once()
    assert save.call_args.args[0] == "vision_debug.png"
    camera.release.assert_called_once()
    if save_result is True:
        assert "Saved warped board" in caplog.text
        assert "Could not save" not in caplog.text
    else:
        assert "Saved warped board" not in caplog.text
        assert "Could not save" in caplog.text
        assert "vision_debug.png" in caplog.text
