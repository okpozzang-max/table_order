"""시드 메뉴 사진 (Wikimedia Commons 이미지 URL, 500px 썸네일).

- 메뉴 이름 -> (이미지 URL, Commons 파일 이름). URL은 파일 이름의 MD5 해시로 만든 `upload.wikimedia.org` 썸네일 경로이다.
- 출처 확인: https://commons.wikimedia.org/wiki/File:<파일 이름> 에서 작성자와 라이선스를 볼 수 있다.
  Commons에 올라온 파일이므로 자유 라이선스(CC BY / CC BY-SA / 퍼블릭 도메인 등)이지만, 라이선스는 파일마다 다르고
  이 목록에서 하나씩 확인하지는 않았다. 데모/개발용이며, 실제 매장에 쓰기 전에는 각 파일의 라이선스(저작자 표시 등)를 확인하거나
  매장의 실제 메뉴 사진으로 교체한다 (관리자 화면에서 이미지 주소를 바꾸면 된다).
- 이미지는 브라우저가 Wikimedia 서버에서 직접 불러온다 (인터넷 연결 필요). 불러오지 못하면 화면이 메뉴명 첫 글자 대체 이미지를 보여 준다.
"""

from __future__ import annotations

import hashlib
import urllib.parse

_BASE = "https://upload.wikimedia.org/wikipedia/commons/thumb"
_WIDTH = 500


def commons_thumb_url(file_title: str, width: int = _WIDTH) -> str:
    """Commons 파일 이름(공백 허용)으로 썸네일 URL을 만든다."""
    name = file_title.replace(" ", "_")
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()  # noqa: S324 (경로 규칙일 뿐 보안 용도 아님)
    quoted = urllib.parse.quote(name, safe="()_.-,")
    return f"{_BASE}/{digest[0]}/{digest[:2]}/{quoted}/{width}px-{quoted}"


# 메뉴 이름 -> Commons 파일 이름
SEED_MENU_IMAGE_FILES: dict[str, str] = {
    "김치찌개": "Korean.food-kimchi.jjiggae-01.jpg",
    "된장찌개": "Doenjang-jjigae.jpg",
    "제육볶음": "Korean barbeque-Maeun dwaeji bulgogi-01.jpg",
    "비빔밥": "Korean.food-Bibimbap-02.jpg",
    "계란말이": "Gyeran-mari 1.jpg",
    "공기밥": "Steamed rice in bowl 01.jpg",
    "김치전": "Korean pancake-Kimchijeon-01.jpg",
    "콜라": "Coca-cola 50cl can - Italia.jpg",
    "사이다": "Korea Chilsung Cider 01 (15891088219).jpg",
    "맥주": "Glass beer mug full.jpg",
    "식혜": "Korean.dessert-Sikhye-01.jpg",
    "아이스크림": "Vanilla ice cream cone.JPG",
}

SEED_MENU_IMAGES: dict[str, str] = {name: commons_thumb_url(title) for name, title in SEED_MENU_IMAGE_FILES.items()}
