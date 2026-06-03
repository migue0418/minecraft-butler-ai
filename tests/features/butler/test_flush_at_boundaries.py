from app.features.butler.service import _flush_at_boundaries


def test_flush_at_sentence_end():
    chunks, rest = _flush_at_boundaries("Hola mundo. Como estas")
    assert chunks == ["Hola mundo."]
    assert rest == "Como estas"


def test_flush_at_exclamation():
    chunks, rest = _flush_at_boundaries("Cuidado! Hay enemigos")
    assert chunks == ["Cuidado!"]
    assert rest == "Hay enemigos"


def test_flush_at_question():
    chunks, rest = _flush_at_boundaries("Tienes hierro? Necesitas mas")
    assert chunks == ["Tienes hierro?"]
    assert rest == "Necesitas mas"


def test_flush_at_newline():
    chunks, rest = _flush_at_boundaries("Primera linea\nSegunda")
    assert len(chunks) >= 1
    assert "Primera linea" in chunks[0]
    assert rest == "Segunda"


def test_no_boundary_returns_empty():
    chunks, rest = _flush_at_boundaries("texto sin frontera")
    assert chunks == []
    assert rest == "texto sin frontera"


def test_multiple_sentences():
    chunks, rest = _flush_at_boundaries("Una. Dos. Tres sin punto")
    assert len(chunks) == 2
    assert "Una." in chunks[0]
    assert "Dos." in chunks[1]
    assert rest == "Tres sin punto"


def test_empty_string():
    chunks, rest = _flush_at_boundaries("")
    assert chunks == []
    assert rest == ""


def test_decimal_not_split():
    # "3.14" no debe dividirse porque no hay espacio tras el punto
    chunks, rest = _flush_at_boundaries("El valor es 3.14 exactamente")
    assert chunks == []
    assert "3.14" in rest


def test_trailing_newline_flushes():
    chunks, rest = _flush_at_boundaries("Linea completa\n")
    assert len(chunks) >= 1
    assert rest == "" or rest.strip() == ""
