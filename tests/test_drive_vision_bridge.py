from coworker.engine import _vision_attachment_message


def test_drive_vision_sidecar_becomes_multimodal_user_input():
    message = _vision_attachment_message(
        {
            "name": "invoice-101.jpg",
            "source": "google_drive:file-101",
            "data_url": "data:image/jpeg;base64,aW52b2ljZQ==",
        }
    )
    assert message is not None
    assert message["role"] == "user"
    assert message["source"] == "google_drive:file-101"
    assert message["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,aW52b2ljZQ=="},
    }
    assert "untrusted data" in message["content"][0]["text"]


def test_drive_vision_sidecar_rejects_non_image_payloads():
    assert _vision_attachment_message({"data_url": "https://example.com/invoice.jpg"}) is None
    assert _vision_attachment_message({"data_url": "data:text/plain;base64,WA=="}) is None
