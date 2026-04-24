from unittest.mock import MagicMock, patch


def _build_messages(query: str):
    from app.engine.multi_agent.direct_prompts import _build_direct_system_messages

    state = {
        "context": {"response_language": "vi"},
        "user_id": "user-1",
    }

    loader = MagicMock()
    loader.build_system_prompt.return_value = "BASE SYSTEM PROMPT"
    loader.get_thinking_instruction.return_value = ""
    loader.get_persona.return_value = {
        "agent": {
            "name": "Wiii",
            "goal": "Tra loi co chat",
            "backstory": "Vai tro: tro ly hoi thoai da linh vuc.",
        }
    }

    with patch("app.prompts.prompt_loader.get_prompt_loader", return_value=loader):
        return _build_direct_system_messages(
            state,
            query,
            "Maritime",
            tools_context_override="",
        )


def test_direct_system_messages_adds_market_analytical_contract():
    messages = _build_messages("phan tich gia dau")

    system_prompt = messages[0].content
    lowered = system_prompt.lower()

    assert "--- nhip phan tich ---" in lowered
    assert "analytical response contract" in lowered
    assert "khong mo dau bang loi chao" in lowered
    assert "khong xin loi dai dong vi thieu du lieu thoi gian thuc" in lowered
    assert "buc tranh hien tai -> cac luc keo chinh -> takeaway/what to watch" in lowered
    assert "khong mo dau bang quan he hoa" in lowered
    assert "mo answer bang mot thesis co the kiem cheo duoc" in lowered
    assert "khong dung danh sach dam/net bold nhu mot ban tom tat tin tuc" in lowered
    assert "base system prompt" not in lowered
    assert "--- visible thinking ---" in lowered
    assert "visible thinking phai nghe nhu wiii dang can lai tin hieu" in lowered
    assert "neu mot truc gia/nguon chua keo duoc" in lowered


def test_direct_system_messages_adds_math_analytical_contract():
    messages = _build_messages("Hay giai thich that sau bai toan toan tu tu lien hop voi compact resolvent")

    system_prompt = messages[0].content
    lowered = system_prompt.lower()

    assert "--- nhip phan tich ---" in lowered
    assert "analytical response contract" in lowered
    assert "khung mac dinh: mo hinh/gia dinh -> phuong trinh hoac suy dan -> y nghia vat ly" in lowered
    assert "truoc khi ket luan" in lowered
    assert "pham vi ma gan dung do con hop le" in lowered
    assert "phuong trinh" in lowered
    assert "base system prompt" not in lowered
    assert "--- visible thinking ---" in lowered
    assert "khung uu tien: mo hinh va gia dinh -> phuong trinh/derivation -> y nghia vat ly" in lowered
    assert "neu cong thuc phu thuoc gia dinh" in lowered
