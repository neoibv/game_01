from giveaway import db, state


def test_encrypt_roundtrip(tmp_path):
    src = tmp_path / "a.db"
    src.write_bytes(b"secret data")
    state.encrypt_file(src, tmp_path / "a.enc", "my passphrase")
    assert b"secret" not in (tmp_path / "a.enc").read_bytes()
    state.decrypt_file(tmp_path / "a.enc", tmp_path / "b.db", "my passphrase")
    assert (tmp_path / "b.db").read_bytes() == b"secret data"


def test_add_event_dedupes(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    kw = dict(source="youtube", source_url="u1", title="t", host="h", matched=["이벤트"], raw_text="r")
    assert db.add_event(conn, **kw) is True
    assert db.add_event(conn, **kw) is False


def test_meta_upsert(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.set_meta(conn, "k", "1")
    db.set_meta(conn, "k", "2")
    assert db.get_meta(conn, "k") == "2"
