"""The engine bridge must expose the v2 story-engine functions."""

def test_engine_exposes_v2_functions():
    from tools import _engine
    assert callable(_engine.search_photos)
    assert callable(_engine.make_session)
    assert callable(_engine.create_project)
    assert callable(_engine.show_project)
    assert callable(_engine.set_timeline)
    assert callable(_engine.default_stories_dir)
