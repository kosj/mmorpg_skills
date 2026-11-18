# 규칙 설명과 수정 방법

수치는 모두 `asset-spec.json`에서 온다. 여기에는 의미와 고치는 방법만 적는다.

| ID | 의미 | 고치는 방법 |
|---|---|---|
| NAME001 | 클래스별 접두사가 없다 (예: StaticMesh는 `SM_`) | 콘텐츠 브라우저에서 이름 변경 후 리디렉터 정리(Fix Up Redirectors) |
| NAME002 | 이름에 허용되지 않는 문자가 있다 (공백, 한글, 특수문자 등) | 영문, 숫자, 밑줄만 쓰도록 이름 변경 |
| TEX001 | 텍스처 가로/세로가 2의 거듭제곱이 아니다 | 원본을 2의 거듭제곱으로 다시 내보내 재임포트. UI처럼 예외 경로면 `power_of_two_exempt_prefixes`에 추가 |
| TEX002 | 텍스처가 경로별 최대 크기를 넘는다 | 원본 축소 또는 텍스처의 Maximum Texture Size 설정. 예외가 정당하면 `max_size_overrides`에 추가 |
| TEX003 | 접미사와 sRGB 설정이 맞지 않는다 (노멀/마스크는 sRGB 꺼짐) | 텍스처 에디터에서 sRGB 체크 수정 |
| TEX004 | 접미사와 압축 설정이 맞지 않는다 | 텍스처 에디터의 Compression Settings 수정 (`_N`은 Normalmap, `_ORM`은 Masks) |
| SM001 | Nanite가 꺼진 메시의 LOD 수가 부족하다 | LOD 자동 생성 또는 Nanite 활성화. 삼각형 수가 면제 기준보다 적으면 검사하지 않는다 |
| SM002 | LOD0 삼각형 수가 예산을 넘는다 | 메시 최적화, Nanite 전환, 또는 메시 분할 |
| SM003 | 단순 콜리전이 없다 | 스태틱 메시 에디터에서 콜리전 추가. 콜리전이 필요 없는 경로면 `collision_exempt_prefixes`에 추가 |
| SM004 | 머티리얼 슬롯이 너무 많다 | 머티리얼 병합 또는 텍스처 아틀라스 |
| GEN001 | 필요한 정보를 수집하지 못해 검사를 건너뛰었다 | 위반이 아님. `collect_assets.py`의 해당 API 호출을 엔진 버전에 맞게 수정 |

## 규칙 추가 방법

1. `collect_assets.py`에서 필요한 사실 정보를 수집해 딕셔너리에 넣는다.
2. `validate.py`에 판정 함수를 추가하고 규칙 ID를 붙인다.
3. `asset-spec.json`에 기준값과 severity를 넣는다.
4. `tests/test_validate.py`에 통과/위반 사례를 하나씩 추가한다.
5. 이 표에 한 줄 추가한다.
