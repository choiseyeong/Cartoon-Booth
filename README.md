<div align="center">
<img width="250" height="378" alt="Image" src="https://github.com/user-attachments/assets/680cd905-c480-43dd-bc53-a7554b819217" />
</div>

## 1. Program Overview (프로그램 개요)

**Cartoon Booth**는 Python의 OpenCV와 PyQt5로 제작된 포토부스 앱입니다.<br>
웹캠으로 직접 촬영하거나 컴퓨터에서 사진을 불러와 카툰 렌더링 필터를 적용하고,<br>
원하는 프레임 레이아웃과 색상으로 꾸며 이미지를 저장할 수 있습니다! 📷💫<br>

이 프로그램은 아래의 단계대로 흘러갑니다.

```
STEP 1 — 프레임 레이아웃 선택
STEP 2 — 사진 촬영 또는 파일 선택
STEP 3 — 프레임 색상 및 카툰 필터 적용 → 저장
```

> `test_cartoon.py`는 카툰 렌더링 코드의 단독으로 테스트 용도이며,<br>
> 메인 앱 흐름과는 무관합니다. 렌터링 코드는 메인 앱과 동일합니다.

### 실행 방법

```bash
# 메인 앱
python main.py

# 카툰 렌더링 테스트 도구 (단독 실행)
python test_cartoon.py
```

---

## 2. Features and Demo (기능과 데모)

### (1) Step 1: 프레임 레이아웃
<img width="480" height="751" alt="Image" src="https://github.com/user-attachments/assets/1f752329-c377-43ca-9031-5b7802e422a9" />

- 세로 4컷, 가로 3컷, 혹은 단일 프레임 레이아웃 중 선택

### (2) Step 2: 촬영 방식

<img width="480" height="747" alt="Image" src="https://github.com/user-attachments/assets/4417fe50-ce35-477d-8298-f4730b222cae" />

![Image](https://github.com/user-attachments/assets/c988d804-3978-405f-959f-b2ca7e2a77b3)

- **웹캠 촬영** — 사진 1장마다 3초 카운트다운 + 흰색 플래시 효과
- **파일 불러오기** — 컴퓨터에서 이미지 선택 (여러 번 나눠서 선택해 누적 가능)
- 촬영된 사진은 썸네일로 표시되며 **개별 삭제(✕)** 가능

### (3) 카툰 렌더링 필터
- OpenCV 기반: 엣지 검출 + 양방향 필터 + 채도 부스트
- Step 2 카메라 미리보기에서 실시간 ON/OFF 전환 가능
- 최종 필터 적용은 **Step 3에서 결정** (이중 적용 방지를 위해 원본은 내부적으로 항상 보존)

### (4) Step 3: 프레임 커스터마이징

<img width="400" height="745" alt="Image" src="https://github.com/user-attachments/assets/f1e62518-782a-4fc1-ab90-b4ec66880b1f"> 

<img width="400" height="745" alt="Image" src="https://github.com/user-attachments/assets/cdc94f6b-6efe-4158-8c8d-e4313ada0f61" />

- 프레임 색상에 따라 검정색 혹은 흰색 로고가 적용된 프레임
- 원본으로 사진을 찍은 경우에도 Step 3에서 카툰 렌더링 필터 적용 가능

### (5) 기타
- 촬영 진행 상황을 나타내는 프로그레스 바
- Step 3에서 색상/필터 변경 시 미리보기 실시간 갱신
- 저장 파일명에 타임스탬프 포함 (`CartoonBooth_MMDD_HHMMSS.png`) — 파일 덮어쓰기 방지

---

## 3. Requirements (필요 라이브러리)


| 패키지 | 버전 |
|--------|-----------|
| Python | >= 3.10 |
| opencv-python | >= 4.13 |
| Pillow | >= 11.2 |
| PyQt5 | >= 5.15 |
| numpy | >= 2.2 |

---

## 4. Development Tools (개발 도구)

🎨 Design
Figma – UI 버튼, 이모지 필터 디자인

🤖 AI Assistance
Claude Code – 코드 보완 및 디버깅 보조

---

## 5. Liminations (한계점)
> 카툰 렌더링으로 만화 느낌을 제대로 표현하지 못하는 이유

### 😸 Good Example

<img width="500" height="647" alt="Image" src="https://github.com/user-attachments/assets/133de084-75c4-4400-9569-bbba813bb62d" />

### 😿 Bad Example

<img width="500" height="648" alt="Image" src="https://github.com/user-attachments/assets/3847cb7c-e0ab-42ec-8a4d-119289db7a93" />

### (1) 피부 톤 구분 없음
피부, 머리카락, 배경을 구분하지 않고 전체에 동일한 필터를 적용합니다.<br>
실제 카툰은 피부는 부드럽게, 윤곽선은 굵게 처리하는 식으로 영역별로 다르게 처리합니다.
### (2) 채도 부스트 단순화
HSV에서 S 채널을 일괄 1.5배 곱하는 방식이라 이미 채도가 높은 영역은 과포화되고,<br>
낮은 영역은 여전히 칙칙하게 보일 수 있습니다.
