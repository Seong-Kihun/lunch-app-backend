# Lunch App

맛집 검색 및 파티 모임 앱

## 설정

### Google Places API 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Places API 활성화
3. API 키 생성
4. `lunch_app_frontend/config.js` 파일에서 `GOOGLE_PLACES_API_KEY` 값을 실제 API 키로 교체

```javascript
// config.js
export const GOOGLE_PLACES_API_KEY = 'your_actual_api_key_here';
```

### 설치 및 실행

```bash
cd lunch_app_frontend
npm install
npm start
```

## 주요 기능

- 🗺️ Google Maps 기반 맛집 검색
- 📍 현재 위치 기반 주변 맛집 찾기
- 🔍 텍스트 검색으로 특정 맛집 검색
- 📝 맛집 리뷰 작성 및 조회
- 🎉 파티 생성 및 참여
- 💬 실시간 채팅

## 기술 스택

- React Native
- Expo
- Google Maps API
- AsyncStorage 