from pathlib import Path

from giveaway.detect import detect, load_filters

FILTERS = load_filters(Path(__file__).resolve().parents[1] / "config/filters.yaml")


def test_matches_event_keywords():
    d = detect("신제품 리뷰 + 구독자 이벤트! 댓글 남기면 추첨해서 증정", FILTERS)
    assert d.is_candidate
    assert {"이벤트", "추첨", "증정"} <= set(d.matched)


def test_plain_video_is_not_candidate():
    assert not detect("RTX 5070 벤치마크 비교", FILTERS).is_candidate


def test_ended_event_only_is_not_candidate():
    assert not detect("지난 이벤트 종료 안내", FILTERS).is_candidate


def test_ended_phrase_with_new_event_stays_candidate():
    d = detect("당첨자 발표 + 새로운 증정 이벤트 시작", FILTERS)
    assert d.is_candidate and "증정" in d.matched
