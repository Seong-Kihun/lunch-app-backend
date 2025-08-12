import React, { useState, useEffect, useRef } from 'react';
import { useNavigation } from '@react-navigation/native';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ScrollView,
  Dimensions,
  Alert,
  ActivityIndicator,
  PanResponder,
  Animated,
  Modal,
  Image,
} from 'react-native';
import MapView, { Marker, PROVIDER_GOOGLE } from 'react-native-maps';
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { GOOGLE_PLACES_API_KEY, DEFAULT_LOCATION, SEARCH_RADIUS } from '../config';
import { processExcelData, calculateDistancesFromCurrentLocation } from '../utils/excelDataProcessor';
import { loadRestaurantData } from '../utils/excelReader';

const { width, height } = Dimensions.get('window');
const SEARCH_BAR_HEIGHT = 72; // 검색창 높이(패딩 포함)
const MIN_LIST_HEIGHT = height * 0.3; // 최소 리스트 높이 (화면의 15%)
const DEFAULT_LIST_HEIGHT = height * 0.6; // 기본 진입시 높이 (화면의 60%)
const MAX_LIST_HEIGHT = height - SEARCH_BAR_HEIGHT + 100; // 최대 리스트 높이 (검색창 바로 아래까지, 둥근 모서리 여유)

const RestaurantMap = (props) => {
  const navigation = useNavigation();
  const currentColors = props.currentColors || {
    primary: '#3B82F6',
    primaryLight: 'rgba(59, 130, 246, 0.1)',
    background: '#F1F5F9',
    surface: '#FFFFFF',
    text: '#1E293B',
    textSecondary: '#64748B',
    border: '#E2E8F0',
    gray: '#64748B',
    lightGray: '#E2E8F0',
    yellow: '#F4D160',
    deepBlue: '#1D5D9B',
    blue: '#3B82F6',
    disabled: '#CBD5E0',
  };
  const [location, setLocation] = useState(null);
  const [restaurants, setRestaurants] = useState([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [sortBy, setSortBy] = useState('distance');
  const [loading, setLoading] = useState(true);
  const mapRef = useRef(null);

  // 애니메이션 값들
  const listHeightAnim = useRef(new Animated.Value(DEFAULT_LIST_HEIGHT)).current;
  const [listHeight, setListHeight] = useState(DEFAULT_LIST_HEIGHT);

  // 필터/정렬 상태
  const [activeCategories, setActiveCategories] = useState([]); // 여러 카테고리 선택
  const [activeSort, setActiveSort] = useState('거리순');
  const categoryOptions = ['한식', '중식', '일식', '양식', '분식', '카페'];
  const sortOptions = ['거리순', '평점순', '리뷰순', '오찬추천순'];
  const [categoryModalVisible, setCategoryModalVisible] = useState(false);
  const [isMapMoved, setIsMapMoved] = useState(false);
  const [mapBounds, setMapBounds] = useState(null);
  const [searchHistory, setSearchHistory] = useState([]);
  const [showSearchHistory, setShowSearchHistory] = useState(false);
  const [mapAreaResults, setMapAreaResults] = useState([]); // 지도 영역 검색 결과
  const [isMapAreaSearch, setIsMapAreaSearch] = useState(false); // 지도 영역 검색 모드
  
  // 페이지네이션 관련 상태
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [displayedRestaurants, setDisplayedRestaurants] = useState([]); // 현재 페이지에 표시될 식당들
  const [mapDisplayedRestaurants, setMapDisplayedRestaurants] = useState([]); // 지도에 표시될 식당들
  const ITEMS_PER_PAGE = 50; // 페이지당 표시할 식당 수

  // Google Places API 검색 함수들
  const searchNearbyRestaurants = async (latitude, longitude, radius = SEARCH_RADIUS) => {
    try {
      console.log('주변 식당 검색 시작:', { latitude, longitude, radius });
      console.log('API URL:', `https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=${latitude},${longitude}&radius=${radius}&type=restaurant&key=${GOOGLE_PLACES_API_KEY}`);
      
      const response = await fetch(
        `https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=${latitude},${longitude}&radius=${radius}&type=restaurant&key=${GOOGLE_PLACES_API_KEY}`
      );
      const data = await response.json();
      
      console.log('Google Places API 응답:', data);
      
      if (data.status === 'OK') {
        const results = data.results.map(place => ({
          id: place.place_id,
          name: place.name,
          address: place.vicinity,
          latitude: place.geometry.location.lat,
          longitude: place.geometry.location.lng,
          // 앱 내부 데이터는 기본값으로 설정
          rating: 0,
          user_ratings_total: 0,
          category: '한식', // 기본값
          distance: 0, // 거리 계산 필요
          recommendCount: 0,
          reviewCount: 0
        }));
        console.log('처리된 주변 식당:', results);
        return results;
      } else {
        console.log('Google Places API 오류:', data.status, data.error_message);
        // API 오류 시 기본 데이터 반환
        console.log('기본 데이터 반환');
        return baseRestaurants;
      }
    } catch (error) {
      console.error('식당 검색 오류:', error);
      console.log('기본 데이터 반환 (에러)');
      return baseRestaurants; // 에러 시 기본 데이터 반환
    }
  };

  const searchRestaurantsInBounds = async (bounds) => {
    try {
      console.log('현재 지도 영역에서 식당 검색 시작');
      console.log('지도 영역:', bounds);
      
      // 지도 범위의 중심점 계산
      const centerLat = (bounds.northeast.lat + bounds.southwest.lat) / 2;
      const centerLng = (bounds.northeast.lng + bounds.southwest.lng) / 2;
      
      // 범위의 반지름 계산 (정확한 거리)
      const latDelta = Math.abs(bounds.northeast.lat - bounds.southwest.lat);
      const lngDelta = Math.abs(bounds.northeast.lng - bounds.southwest.lng);
      
      // 위도 1도 ≈ 111km, 경도 1도 ≈ 88.9km (한반도 기준)
      const latRadius = latDelta * 111.0 / 2; // 반지름이므로 2로 나눔
      const lngRadius = lngDelta * 88.9 / 2;
      const radius = Math.max(latRadius, lngRadius);
      
      console.log('검색 중심점:', centerLat, centerLng);
      console.log('검색 반지름:', radius, 'km');
      
      // 서버 API로 현재 지도 영역 내 식당 검색
      const response = await fetch(
        `https://lunch-app-backend-ra12.onrender.com/restaurants?lat=${centerLat}&lon=${centerLng}&radius=${Math.min(radius, 50)}`
      );
      const data = await response.json();
      
      if (data && data.restaurants && data.restaurants.length > 0) {
        console.log('지도 영역 내 식당 검색 결과:', data.restaurants.length, '개');
        return data.restaurants.map(restaurant => ({
          id: restaurant.id,
          name: restaurant.name,
          address: restaurant.address,
          latitude: restaurant.latitude,
          longitude: restaurant.longitude,
          category: restaurant.category || '기타',
          rating: restaurant.rating || 0,
          user_ratings_total: restaurant.review_count || 0,
          distance: 0,
          recommendCount: 0,
          reviewCount: restaurant.review_count || 0
        }));
      }
      
      console.log('지도 영역 내 식당 없음');
      return [];
    } catch (error) {
      console.error('지도 영역 검색 오류:', error);
      return [];
    }
  };

  const saveSearchHistory = (query) => {
    if (query.trim()) {
      const newHistory = [query, ...searchHistory.filter(h => h !== query)].slice(0, 5);
      setSearchHistory(newHistory);
      AsyncStorage.setItem('searchHistory', JSON.stringify(newHistory));
    }
  };

  const loadSearchHistory = async () => {
    try {
      const history = await AsyncStorage.getItem('searchHistory');
      if (history) {
        setSearchHistory(JSON.parse(history));
      }
    } catch (error) {
      console.error('검색 히스토리 로드 오류:', error);
    }
  };

  const searchRestaurantsByQuery = async (query) => {
    try {
      console.log('검색 쿼리:', query);
      
      // 카테고리는 사용자 리뷰에서 자동으로 결정되므로 여기서는 감지하지 않음
      console.log('검색 쿼리:', query);
      
      // Google Places API로 먼저 검색
      try {
        console.log('Google Places API 검색 시작');
        const response = await fetch(
          `https://maps.googleapis.com/maps/api/place/textsearch/json?query=${encodeURIComponent(query)}&type=restaurant&key=${GOOGLE_PLACES_API_KEY}`
        );
        const data = await response.json();
        
        console.log('Google Places API 응답:', data);
        
        if (data.status === 'OK' && data.results.length > 0) {
          const results = data.results.map(place => ({
            id: place.place_id,
            name: place.name,
            address: place.formatted_address,
            latitude: place.geometry.location.lat,
            longitude: place.geometry.location.lng,
            // 앱 내부 데이터는 기본값으로 설정
            rating: 0,
            user_ratings_total: 0,
            category: detectedCategory,
            distance: 0,
            recommendCount: 0,
            reviewCount: 0
          }));
          console.log('Google Places API 검색 결과:', results);
          return results;
        } else {
          console.log('Google Places API 검색 결과 없음:', data.status, data.error_message);
        }
      } catch (apiError) {
        console.error('Google Places API 오류:', apiError);
      }
      
      // Google Places API에서 찾지 못한 경우 서버 데이터에서 검색
      console.log('서버 데이터에서 검색 시도');
      try {
        const response = await fetch(`https://lunch-app-backend-ra12.onrender.com/restaurants?query=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data && data.restaurants && data.restaurants.length > 0) {
          console.log('서버 데이터에서 검색 결과:', data.restaurants);
          return data.restaurants.map(restaurant => ({
            id: restaurant.id,
            name: restaurant.name,
            address: restaurant.address,
            category: restaurant.category || '기타',
            rating: restaurant.rating || 0,
            user_ratings_total: restaurant.review_count || 0,
            latitude: restaurant.latitude || 37.5013,
            longitude: restaurant.longitude || 127.0396,
            distance: 0,
            recommendCount: 0,
            reviewCount: restaurant.review_count || 0
          }));
        }
      } catch (serverError) {
        console.error('서버 검색 오류:', serverError);
        // 서버 오류 시 로컬 CSV 데이터로 백업
        console.log('로컬 CSV 데이터로 백업 검색');
        const excelData = await loadRestaurantData();
        const processedData = await processExcelData(excelData);
        const excelResults = processedData.filter(restaurant => 
          restaurant.name.toLowerCase().includes(query.toLowerCase()) ||
          restaurant.category.toLowerCase().includes(query.toLowerCase()) ||
          restaurant.address.toLowerCase().includes(query.toLowerCase())
        );
        
        if (excelResults.length > 0) {
          console.log('엑셀 데이터에서 검색 결과:', excelResults);
          return excelResults.map(restaurant => ({
            ...restaurant,
            category: restaurant.category || '기타'
          }));
        }
      }
      
      console.log('검색 결과 없음');
      return [];
    } catch (error) {
      console.error('검색 오류:', error);
      return [];
    }
  };

  // 거리 계산 함수
  const calculateDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371; // 지구의 반지름 (km)
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  };

  // 페이지네이션 함수들
  const updatePagination = (allRestaurants) => {
    const total = allRestaurants.length;
    const pages = Math.ceil(total / ITEMS_PER_PAGE);
    setTotalPages(pages);
    setCurrentPage(1);
    
    // 첫 번째 페이지 식당들
    const firstPageRestaurants = allRestaurants.slice(0, ITEMS_PER_PAGE);
    setDisplayedRestaurants(firstPageRestaurants);
    
    // 지도에 표시할 식당들 (목록과 동일하게)
    setMapDisplayedRestaurants(firstPageRestaurants);
    
    // 전체 데이터 저장 (페이지네이션용)
    setRestaurants(allRestaurants);
    
    console.log(`페이지네이션 업데이트: 전체 ${total}개, 페이지 ${pages}개, 첫 페이지 ${firstPageRestaurants.length}개`);
  };

  const goToNextPage = () => {
    const totalPages = Math.ceil(restaurants.length / ITEMS_PER_PAGE);
    if (currentPage < totalPages) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      
      // 현재 페이지의 식당들 가져오기
      const startIndex = (nextPage - 1) * ITEMS_PER_PAGE;
      const endIndex = startIndex + ITEMS_PER_PAGE;
      const pageRestaurants = restaurants.slice(startIndex, endIndex);
      setDisplayedRestaurants(pageRestaurants);
      
      // 지도 마커도 업데이트 (중요!)
      setMapDisplayedRestaurants(pageRestaurants);
      
      console.log('다음 페이지로 이동:', nextPage, '페이지의 식당들:', pageRestaurants.length, '개');
      console.log('지도 마커 업데이트됨:', pageRestaurants.map(r => r.name).join(', '));
    }
  };

  const goToPreviousPage = () => {
    if (currentPage > 1) {
      const prevPage = currentPage - 1;
      setCurrentPage(prevPage);
      
      // 현재 페이지의 식당들 가져오기
      const startIndex = (prevPage - 1) * ITEMS_PER_PAGE;
      const endIndex = startIndex + ITEMS_PER_PAGE;
      const pageRestaurants = restaurants.slice(startIndex, endIndex);
      setDisplayedRestaurants(pageRestaurants);
      
      // 지도 마커도 업데이트 (중요!)
      setMapDisplayedRestaurants(pageRestaurants);
      
      console.log('이전 페이지로 이동:', prevPage, '페이지의 식당들:', pageRestaurants.length, '개');
      console.log('지도 마커 업데이트됨:', pageRestaurants.map(r => r.name).join(', '));
    }
  };

  const goToPage = (pageNumber) => {
    const totalPages = Math.ceil(restaurants.length / ITEMS_PER_PAGE);
    if (pageNumber >= 1 && pageNumber <= totalPages) {
      setCurrentPage(pageNumber);
      
      // 현재 페이지의 식당들 가져오기
      const startIndex = (pageNumber - 1) * ITEMS_PER_PAGE;
      const endIndex = startIndex + ITEMS_PER_PAGE;
      const pageRestaurants = restaurants.slice(startIndex, endIndex);
      setDisplayedRestaurants(pageRestaurants);
      
      // 지도 마커도 업데이트 (중요!)
      setMapDisplayedRestaurants(pageRestaurants);
      
      console.log('페이지 이동:', pageNumber, '페이지의 식당들:', pageRestaurants.length, '개');
      console.log('지도 마커 업데이트됨:', pageRestaurants.map(r => r.name).join(', '));
    }
  };

  // 기본 식당 데이터 (위치 정보만 포함)
  const baseRestaurants = [
    {
      id: 1,
      name: '맛있는 한식당',
      category: '한식',
      distance: 0.2,
      latitude: 37.5665,
      longitude: 126.9780,
      address: '서울시 강남구 테헤란로 123',
      rating: 4.5,
      user_ratings_total: 128,
      recommendCount: 15,
      reviewCount: 45
    },
    {
      id: 2,
      name: '신선한 중식당',
      category: '중식',
      distance: 0.5,
      latitude: 37.5670,
      longitude: 126.9785,
      address: '서울시 강남구 역삼동 456',
      rating: 4.2,
      user_ratings_total: 89,
      recommendCount: 12,
      reviewCount: 34
    },
    {
      id: 3,
      name: '고급 일식당',
      category: '일식',
      distance: 0.8,
      latitude: 37.5660,
      longitude: 126.9775,
      address: '서울시 강남구 삼성동 789',
      rating: 4.8,
      user_ratings_total: 156,
      recommendCount: 23,
      reviewCount: 67
    },
    {
      id: 4,
      name: '분식천국',
      category: '분식',
      distance: 1.2,
      latitude: 37.5680,
      longitude: 126.9790,
      address: '서울시 강남구 논현동 321',
      rating: 4.0,
      user_ratings_total: 92,
      recommendCount: 8,
      reviewCount: 28
    },
    {
      id: 5,
      name: '피자헛',
      category: '양식',
      distance: 1.5,
      latitude: 37.5650,
      longitude: 126.9765,
      address: '서울시 강남구 청담동 654',
      rating: 4.3,
      user_ratings_total: 73,
      recommendCount: 19,
      reviewCount: 41
    },
    {
      id: 6,
      name: '스타벅스 강남점',
      category: '카페',
      distance: 0.3,
      latitude: 37.5668,
      longitude: 126.9782,
      address: '서울시 강남구 신사동 111',
      rating: 4.6,
      user_ratings_total: 203,
      recommendCount: 31,
      reviewCount: 89
    },
    {
      id: 7,
      name: '김치찌개 전문점',
      category: '한식',
      distance: 0.7,
      latitude: 37.5662,
      longitude: 126.9778,
      address: '서울시 강남구 압구정동 222',
      rating: 4.4,
      user_ratings_total: 67,
      recommendCount: 14,
      reviewCount: 52
    },
    {
      id: 8,
      name: '초밥집',
      category: '일식',
      distance: 1.0,
      latitude: 37.5675,
      longitude: 126.9788,
      address: '서울시 강남구 도산대로 333',
      rating: 4.7,
      user_ratings_total: 134,
      recommendCount: 27,
      reviewCount: 76
    },
    {
      id: 9,
      name: '떡볶이 가게',
      category: '분식',
      distance: 0.4,
      latitude: 37.5669,
      longitude: 126.9781,
      address: '서울시 강남구 청담대로 444',
      rating: 4.1,
      user_ratings_total: 98,
      recommendCount: 11,
      reviewCount: 38
    },
    {
      id: 10,
      name: '파스타 전문점',
      category: '양식',
      distance: 0.9,
      latitude: 37.5672,
      longitude: 126.9786,
      address: '서울시 강남구 강남대로 555',
      rating: 4.2,
      user_ratings_total: 156,
      recommendCount: 22,
      reviewCount: 63
    },
    {
      id: 11,
      name: '삼겹살 맛집',
      category: '한식',
      distance: 0.6,
      latitude: 37.5667,
      longitude: 126.9787,
      address: '서울시 강남구 가로수길 666',
      rating: 4.3,
      user_ratings_total: 87,
      recommendCount: 18,
      reviewCount: 45
    },
    {
      id: 12,
      name: '라멘 전문점',
      category: '일식',
      distance: 1.1,
      latitude: 37.5673,
      longitude: 126.9793,
      address: '서울시 강남구 신사대로 777',
      rating: 4.5,
      user_ratings_total: 112,
      recommendCount: 25,
      reviewCount: 71
    },
    {
      id: 13,
      name: '스테이크 하우스',
      category: '양식',
      distance: 0.8,
      latitude: 37.5664,
      longitude: 126.9784,
      address: '서울시 강남구 압구정로 888',
      rating: 4.4,
      user_ratings_total: 145,
      recommendCount: 29,
      reviewCount: 83
    },
    {
      id: 14,
      name: '짜장면 맛집',
      category: '중식',
      distance: 1.3,
      latitude: 37.5678,
      longitude: 126.9798,
      address: '서울시 강남구 청담로 999',
      rating: 4.0,
      user_ratings_total: 76,
      recommendCount: 9,
      reviewCount: 31
    },
    {
      id: 15,
      name: '투썸플레이스',
      category: '카페',
      distance: 0.5,
      latitude: 37.5666,
      longitude: 126.9786,
      address: '서울시 강남구 테헤란로 101',
      rating: 4.1,
      user_ratings_total: 94,
      recommendCount: 13,
      reviewCount: 42
    }
  ];

  useEffect(() => {
    // 지도 영역 검색 모드가 아닐 때만 현재 위치 가져오기
    if (!isMapAreaSearch) {
      getCurrentLocation();
    }
    loadSearchHistory();
    setLoading(false);
  }, [isMapAreaSearch]);

  const getCurrentLocation = async () => {
    try {
      setLoading(true);
      
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('위치 권한', '위치 권한이 필요합니다.');
        setLocation(DEFAULT_LOCATION);
        // 로컬 CSV 데이터 처리
        const excelData = await loadRestaurantData();
        const processedData = await processExcelData(excelData);
        const restaurantsWithDistance = calculateDistancesFromCurrentLocation(
          processedData, 
          DEFAULT_LOCATION.latitude, 
          DEFAULT_LOCATION.longitude
        );
        setRestaurants(restaurantsWithDistance);
        setLoading(false);
        return;
      }

      const currentLocation = await Location.getCurrentPositionAsync({});
      const newLocation = {
        latitude: currentLocation.coords.latitude,
        longitude: currentLocation.coords.longitude,
      };
      
      setLocation(newLocation);
      console.log('현재 위치:', newLocation);
      
      // 로컬 CSV 데이터 처리
      console.log('로컬 CSV 데이터 처리 시작...');
      const excelData = await loadRestaurantData();
      const processedData = await processExcelData(excelData);
      console.log('처리된 CSV 데이터:', processedData);
      
      // 거리 계산 추가
      const restaurantsWithDistance = calculateDistancesFromCurrentLocation(
        processedData,
        newLocation.latitude,
        newLocation.longitude
      );
      
      setRestaurants(restaurantsWithDistance);
      
      // 페이지네이션 초기화
      updatePagination(restaurantsWithDistance);
      
      // 지도 영역 검색 모드가 아닐 때만 지도 이동
      if (mapRef.current && !isMapAreaSearch) {
        mapRef.current.animateToRegion({
          latitude: newLocation.latitude,
          longitude: newLocation.longitude,
          latitudeDelta: 0.01,
          longitudeDelta: 0.01,
        }, 1000);
      }
      
      setLoading(false);
      
    } catch (error) {
      console.log('위치 가져오기 실패:', error);
      Alert.alert('위치 오류', '현재 위치를 가져올 수 없습니다.');
      // 기본 위치 설정
      setLocation(DEFAULT_LOCATION);
      const excelData = await loadRestaurantData();
      const processedData = await processExcelData(excelData);
      const restaurantsWithDistance = calculateDistancesFromCurrentLocation(
        processedData,
        DEFAULT_LOCATION.latitude,
        DEFAULT_LOCATION.longitude
      );
      setRestaurants(restaurantsWithDistance);
      
      // 페이지네이션 초기화
      updatePagination(restaurantsWithDistance);
      
      setLoading(false);
    }
  };

  const handleMarkerPress = (restaurant) => {
    setSelectedRestaurant(restaurant);
  };

  const handleRestaurantPress = (restaurant) => {
    navigation.navigate('RestaurantDetail', { restaurant });
  };



  const [restaurantsWithData, setRestaurantsWithData] = useState([]);

  // 각 식당의 오찬 추천 데이터를 가져오는 함수
  const fetchRestaurantLunchRecommendData = async (restaurantId) => {
    try {
      const storedData = await AsyncStorage.getItem(`lunch_recommend_${restaurantId}`);
      if (storedData) {
        const parsedData = JSON.parse(storedData);
        return parsedData.recommendCount || 0;
      }
      return 0;
    } catch (error) {
      console.error('오찬 추천 데이터 로드 오류:', error);
      return 0;
    }
  };

  // 모든 식당의 데이터를 로드하는 함수
  const loadRestaurantsData = async () => {
    // 지도 영역 검색 모드일 때는 실행하지 않음
    if (isMapAreaSearch) {
      console.log('지도 영역 검색 모드 - 데이터 로드 건너뜀');
      return;
    }
    
    try {
      console.log('서버에서 식당 데이터 로드 시작...');
      
      // 서버 API에서 식당 데이터 가져오기 (현재 위치 기반)
      let apiUrl = 'https://lunch-app-backend-ra12.onrender.com/restaurants';
      
      // 현재 위치가 있으면 지역 필터 적용
      if (location) {
        apiUrl += `?lat=${location.latitude}&lon=${location.longitude}&radius=10`;
      }
      
      const response = await fetch(apiUrl);
      const data = await response.json();
      
      console.log('서버에서 받은 식당 데이터:', data);
      
      if (data && data.restaurants && data.restaurants.length > 0) {
        // 서버 데이터를 앱 형식으로 변환 (주소를 좌표로 변환)
        const processedData = await Promise.all(data.restaurants.map(async (restaurant, index) => {
          let latitude = restaurant.latitude;
          let longitude = restaurant.longitude;
          
          // 좌표가 없으면 주소를 좌표로 변환
          if (!latitude || !longitude) {
            try {
              const geocodeResponse = await fetch(
                `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(restaurant.address)}&key=${GOOGLE_PLACES_API_KEY}`
              );
              const geocodeData = await geocodeResponse.json();
              
              if (geocodeData.results && geocodeData.results.length > 0) {
                const location = geocodeData.results[0].geometry.location;
                latitude = location.lat;
                longitude = location.lng;
                console.log(`${restaurant.name} 좌표 변환 성공:`, latitude, longitude);
              } else {
                console.log(`${restaurant.name} 좌표 변환 실패, 기본값 사용`);
                latitude = 37.5013;
                longitude = 127.0396;
              }
            } catch (error) {
              console.error(`${restaurant.name} 좌표 변환 오류:`, error);
              latitude = 37.5013;
              longitude = 127.0396;
            }
          }
          
          return {
            id: restaurant.id,
            name: restaurant.name,
            address: restaurant.address,
            category: restaurant.category || '기타',
            rating: restaurant.avg_rating || 0,
            user_ratings_total: restaurant.review_count || 0,
            latitude: latitude,
            longitude: longitude,
            distance: 0, // 거리는 나중에 계산
            recommendCount: 0,
            reviewCount: restaurant.review_count || 0
          };
        }));
        
        console.log('처리된 서버 데이터:', processedData);
        
        // 현재 위치 기준으로 거리 계산
        if (location) {
          const dataWithDistance = calculateDistancesFromCurrentLocation(
            processedData, 
            location.latitude, 
            location.longitude
          );
          setRestaurants(dataWithDistance);
        } else {
          setRestaurants(processedData);
        }
        
        // 추천 데이터 추가
        const restaurantsWithRecommendData = await Promise.all(
          processedData.map(async (restaurant) => {
            const recommendCount = await fetchRestaurantLunchRecommendData(restaurant.id);
            return {
              ...restaurant,
              recommendCount
            };
          })
        );
        setRestaurantsWithData(restaurantsWithRecommendData);
      } else {
        console.log('서버 데이터가 없습니다.');
        console.log('총 식당 수:', data.total || 0);
        setRestaurants([]);
        setRestaurantsWithData([]);
      }
    } catch (error) {
      console.error('서버에서 식당 데이터 로드 오류:', error);
      // 서버 오류 시 로컬 CSV 파일 사용 (백업)
      try {
        console.log('로컬 CSV 데이터로 백업...');
        const csvData = await loadRestaurantData();
        if (csvData && csvData.length > 0) {
          const processedData = await processExcelData(csvData);
          if (location) {
            const dataWithDistance = calculateDistancesFromCurrentLocation(
              processedData, 
              location.latitude, 
              location.longitude
            );
            setRestaurants(dataWithDistance);
          } else {
            setRestaurants(processedData);
          }
          
          // 추천 데이터 추가
          const restaurantsWithRecommendData = await Promise.all(
            processedData.map(async (restaurant) => {
              const recommendCount = await fetchRestaurantLunchRecommendData(restaurant.id);
              return {
                ...restaurant,
                recommendCount
              };
            })
          );
          setRestaurantsWithData(restaurantsWithRecommendData);
        } else {
          setRestaurants([]);
          setRestaurantsWithData([]);
        }
      } catch (backupError) {
        console.error('백업 데이터 로드도 실패:', backupError);
        setRestaurants([]);
        setRestaurantsWithData([]);
      }
    }
  };

  // 초기 데이터 로드 (한 번만 실행)
  useEffect(() => {
    if (!isMapAreaSearch) {
      loadRestaurantsData();
    }
  }, [isMapAreaSearch]); // isMapAreaSearch가 변경될 때마다 체크

  // 지도 영역 검색 모드일 때는 해당 결과를 우선 표시
  const displayRestaurants = isMapAreaSearch ? mapAreaResults : displayedRestaurants;
  
  const filteredAndSortedRestaurants = displayRestaurants
    .filter(restaurant => {
      const matchesSearch = restaurant.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           restaurant.category.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = activeCategories.length === 0 || activeCategories.includes(restaurant.category);
      return matchesSearch && matchesCategory;
    })
    .sort((a, b) => {
      switch (activeSort) {
        case '거리순':
          return a.distance - b.distance;
        case '평점순':
          return b.rating - a.rating;
        case '리뷰순':
          return b.reviewCount - a.reviewCount;
        case '오찬추천순':
          return b.recommendCount - a.recommendCount;
        default:
          return a.distance - b.distance;
      }
    });

  // PanResponder 설정
  const panResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: () => {
      // 드래그 시작
    },
    onPanResponderMove: (evt, gestureState) => {
      const newHeight = listHeight - gestureState.dy;
      if (newHeight >= MIN_LIST_HEIGHT && newHeight <= MAX_LIST_HEIGHT) {
        setListHeight(newHeight);
        listHeightAnim.setValue(newHeight);
      }
    },
    onPanResponderRelease: (evt, gestureState) => {
      const velocity = gestureState.vy;
      const currentHeight = listHeight;
      // 3단계 스냅: MIN, DEFAULT, MAX
      // 기준점 계산
      const mid1 = (MIN_LIST_HEIGHT + DEFAULT_LIST_HEIGHT) / 2;
      const mid2 = (DEFAULT_LIST_HEIGHT + MAX_LIST_HEIGHT) / 2;
      let targetHeight;
      if (currentHeight < mid1) {
        targetHeight = MIN_LIST_HEIGHT;
      } else if (currentHeight < mid2) {
        targetHeight = DEFAULT_LIST_HEIGHT;
      } else {
        targetHeight = MAX_LIST_HEIGHT;
      }
        Animated.spring(listHeightAnim, {
        toValue: targetHeight,
          useNativeDriver: false,
        }).start();
      setListHeight(targetHeight);
    },
  });

  const RestaurantCard = ({ restaurant }) => {
    const [restaurantData, setRestaurantData] = useState({
      reviews: [],
      averageRating: 0,
      reviewCount: 0,
      mostSelectedFoodTypes: [],
      topKeywords: [],
      latestImage: null
    });
    const [distance, setDistance] = useState(null);

    // 거리 계산 함수
    const calculateDistance = (lat1, lon1, lat2, lon2) => {
      const R = 6371; // 지구의 반지름 (km)
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      const distance = R * c;
      return distance;
    };

    useEffect(() => {
      const fetchRestaurantData = async () => {
        try {
          // 리뷰 데이터 가져오기
          const storedReviews = await AsyncStorage.getItem(`reviews_${restaurant.id}`);
          
          if (storedReviews) {
            const parsedReviews = JSON.parse(storedReviews);
            
            // 평균 평점 계산
            const averageRating = parsedReviews.length > 0 
              ? (parsedReviews.reduce((sum, review) => sum + review.rating, 0) / parsedReviews.length).toFixed(1)
              : 0;
            
            // 가장 많이 선택된 음식 종류 계산
            const foodTypeCount = {};
            parsedReviews.forEach(review => {
              if (review.food_types && review.food_types.length > 0) {
                review.food_types.forEach(foodType => {
                  foodTypeCount[foodType] = (foodTypeCount[foodType] || 0) + 1;
                });
              }
            });
            
            let maxCount = 0;
            const mostSelectedTypes = [];
            Object.keys(foodTypeCount).forEach(foodType => {
              if (foodTypeCount[foodType] > maxCount) {
                maxCount = foodTypeCount[foodType];
              }
            });
            Object.keys(foodTypeCount).forEach(foodType => {
              if (foodTypeCount[foodType] === maxCount && maxCount > 0) {
                mostSelectedTypes.push(foodType);
              }
            });
            
            // 키워드 계산
            const keywordCount = {};
            parsedReviews.forEach(review => {
              if (review.atmosphere && review.atmosphere.length > 0) {
                review.atmosphere.forEach(keyword => {
                  keywordCount[keyword] = (keywordCount[keyword] || 0) + 1;
                });
              }
              if (review.features && review.features.length > 0) {
                review.features.forEach(keyword => {
                  keywordCount[keyword] = (keywordCount[keyword] || 0) + 1;
                });
              }
            });
            
            const topKeywords = Object.keys(keywordCount)
              .sort((a, b) => keywordCount[b] - keywordCount[a])
              .slice(0, 3);
            
            // 최신 이미지 찾기
            let latestImage = null;
            if (parsedReviews.length > 0) {
              const sortedReviews = [...parsedReviews].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
              for (let review of sortedReviews) {
                if (review.images && review.images.length > 0) {
                  latestImage = review.images[0];
                  break;
                }
              }
            }
            
            setRestaurantData({
              reviews: parsedReviews,
              averageRating: parseFloat(averageRating),
              reviewCount: parsedReviews.length,
              mostSelectedFoodTypes: mostSelectedTypes,
              topKeywords: topKeywords,
              latestImage: latestImage
            });
          } else {
            setRestaurantData({
              reviews: [],
              averageRating: 0,
              reviewCount: 0,
              mostSelectedFoodTypes: [],
              topKeywords: [],
              latestImage: null
            });
          }

          // 거리 계산
          if (restaurant.latitude && restaurant.longitude) {
            const currentLat = 37.5665;
            const currentLon = 126.9780;
            const calculatedDistance = calculateDistance(
              currentLat, currentLon,
              restaurant.latitude, restaurant.longitude
            );
            setDistance(calculatedDistance);
          }
        } catch (error) {
          console.error('식당 데이터 로드 오류:', error);
        }
      };

      fetchRestaurantData();
    }, [restaurant.id]);

    return (
      <TouchableOpacity
        key={restaurant.id}
        style={{
          backgroundColor: currentColors.surface,
          borderRadius: 16,
          marginHorizontal: 16,
          marginBottom: 12,
          padding: 16,
          elevation: 2,
          shadowColor: currentColors.primary,
          shadowOffset: { width: 0, height: 2 },
          shadowOpacity: 0.1,
          shadowRadius: 4,
          borderWidth: 1,
          borderColor: currentColors.lightGray
        }}
        onPress={() => handleRestaurantPress(restaurant)}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          {/* 최신 이미지 */}
          <View style={{ width: 54, height: 54, borderRadius: 12, marginRight: 14, overflow: 'hidden' }}>
            {restaurantData.latestImage ? (
              <Image 
                source={{ uri: restaurantData.latestImage }} 
                style={{ width: 54, height: 54, borderRadius: 12 }}
                resizeMode="cover"
              />
            ) : (
              <View style={{ 
                width: 54, 
                height: 54, 
                borderRadius: 12, 
                backgroundColor: currentColors.background, 
                justifyContent: 'center', 
                alignItems: 'center' 
              }}>
                <Text style={{ fontSize: 26 }}>🍽️</Text>
              </View>
            )}
          </View>
          
          <View style={{ flex: 1 }}>
            {/* 식당 이름과 음식 종류 */}
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 6 }}>
              <Text style={{ fontSize: 17, fontWeight: 'bold', color: currentColors.text, flex: 1 }}>
                {restaurant.name}
              </Text>
              {restaurantData.mostSelectedFoodTypes.length > 0 && (
                <View style={{
                  backgroundColor: currentColors.primary,
                  borderRadius: 16,
                  paddingHorizontal: 12,
                  paddingVertical: 6,
                  marginLeft: 8
                }}>
                  <Text style={{ color: '#fff', fontWeight: 'bold', fontSize: 12 }}>
                    {restaurantData.mostSelectedFoodTypes[0]}
                  </Text>
                </View>
              )}
            </View>
            
            {/* 별점, 리뷰 수, 거리 */}
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 6 }}>
              <Ionicons name="star" size={14} color={currentColors.yellow} style={{ marginRight: 2 }} />
              <Text style={{ fontSize: 14, fontWeight: 'bold', color: currentColors.text }}>
                {restaurantData.reviewCount > 0 ? restaurantData.averageRating.toFixed(1) : '0.0'}
              </Text>
              <Text style={{ fontSize: 13, color: currentColors.textSecondary, marginLeft: 4 }}>
                ({restaurantData.reviewCount})
              </Text>
              {distance !== null && (
                <Text style={{ fontSize: 13, color: currentColors.textSecondary, marginLeft: 10 }}>
                  {distance < 1 ? `${(distance * 1000).toFixed(0)}m` : `${distance.toFixed(1)}km`}
                </Text>
              )}
            </View>
            
            {/* 주소 */}
            <Text style={{ 
              color: currentColors.textSecondary, 
              fontSize: 12, 
              marginTop: 4
            }}>
              {restaurant.address}
            </Text>
            
            {/* 키워드 */}
            {restaurantData.topKeywords.length > 0 && (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginTop: 4 }}>
                {restaurantData.topKeywords.slice(0, 3).map((keyword, index) => (
                  <Text key={index} style={{ 
                    color: currentColors.textSecondary, 
                    fontSize: 12, 
                    marginRight: 8,
                    marginBottom: 4
                  }}>
                    #{keyword}
                  </Text>
                ))}
              </View>
            )}
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  const renderRestaurantCard = (restaurant) => (
    <RestaurantCard restaurant={restaurant} />
  );

  const renderFilterButton = (type, label) => (
    <TouchableOpacity
      style={[
        styles.filterButton,
        filterType === type && { backgroundColor: currentColors.yellow, borderColor: currentColors.yellow }
      ]}
      onPress={() => setFilterType(type)}
    >
      <Text style={[
        styles.filterButtonText,
        filterType === type && { color: currentColors.text, fontWeight: '600' }
      ]}>
        {label}
      </Text>
    </TouchableOpacity>
  );

  const renderSortButton = (type, label) => (
    <TouchableOpacity
      style={[
        styles.sortButton,
        sortBy === type && { backgroundColor: currentColors.deepBlue, borderColor: currentColors.deepBlue }
      ]}
      onPress={() => setSortBy(type)}
    >
      <Text style={[
        styles.sortButtonText,
        sortBy === type && { color: '#fff', fontWeight: '600' }
      ]}>
        {label}
      </Text>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: currentColors.background }]}>
        <ActivityIndicator size="large" color={currentColors.yellow} />
        <Text style={[styles.loadingText, { color: currentColors.textSecondary }]}>맛집을 찾고 있습니다...</Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: currentColors.background }]}>
      <TouchableOpacity
        style={{ flex: 1 }}
        activeOpacity={1}
        onPress={() => setShowSearchHistory(false)}
      >
      {/* 검색창 */}
      <View style={[styles.searchContainer, { backgroundColor: currentColors.surface, borderBottomColor: currentColors.border }]}>
        <View style={[styles.searchInputContainer, { backgroundColor: currentColors.background }]}>
          <Ionicons name="search" size={20} color={currentColors.gray} style={styles.searchIcon} />
          <TextInput
            style={[styles.searchInput, { color: currentColors.text }]}
            placeholder="지역, 맛집을 검색해보세요"
            value={searchQuery}
            onChangeText={(text) => {
              setSearchQuery(text);
              setShowSearchHistory(text.length === 0 && searchHistory.length > 0);
              // 검색어가 변경되면 지도 영역 검색 모드 해제
              if (text.length > 0) {
                setIsMapAreaSearch(false);
                setMapAreaResults([]);
              }
            }}
            onFocus={() => {
              if (searchHistory.length > 0) {
                setShowSearchHistory(true);
              }
            }}
            placeholderTextColor={currentColors.textSecondary}
            onSubmitEditing={async () => {
              if (searchQuery.trim()) {
                console.log('검색 시작:', searchQuery);
                saveSearchHistory(searchQuery);
                // 지도 영역 검색 모드 해제
                setIsMapAreaSearch(false);
                setMapAreaResults([]);
                setLoading(true);
                const searchResults = await searchRestaurantsByQuery(searchQuery);
                console.log('검색 결과:', searchResults);
                
                if (searchResults.length > 0) {
                  const restaurantsWithDistance = searchResults.map(restaurant => ({
                    ...restaurant,
                    distance: location ? calculateDistance(
                      location.latitude,
                      location.longitude,
                      restaurant.latitude,
                      restaurant.longitude
                    ) : 0
                  }));
                  setRestaurants(restaurantsWithDistance);
                  console.log('식당 목록 업데이트:', restaurantsWithDistance.length);
                } else {
                  console.log('검색 결과가 없습니다.');
                  Alert.alert('검색 결과 없음', '검색어에 맞는 식당을 찾을 수 없습니다.');
                }
                setShowSearchHistory(false);
                setLoading(false);
              }
            }}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity
                          onPress={() => {
              setSearchQuery('');
              setShowSearchHistory(false);
              // 지도 영역 검색 모드 해제하고 현재 위치로 다시 검색
              setIsMapAreaSearch(false);
              setMapAreaResults([]);
              // getCurrentLocation() 호출하지 않음 - 지도 위치 유지
            }}
              style={{ padding: 8 }}
            >
              <Ionicons name="close-circle" size={20} color={currentColors.gray} />
            </TouchableOpacity>
          )}
        </View>

        {/* 검색 히스토리 */}
        {showSearchHistory && searchHistory.length > 0 && (
          <View style={[styles.searchHistoryContainer, { backgroundColor: currentColors.surface }]}>
            <Text style={[styles.searchHistoryTitle, { color: currentColors.textSecondary }]}>
              최근 검색어
            </Text>
            {searchHistory.map((historyItem, index) => (
              <TouchableOpacity
                key={index}
                style={styles.searchHistoryItem}
                onPress={async () => {
                  setSearchQuery(historyItem);
                  setShowSearchHistory(false);
                  // 지도 영역 검색 모드 해제
                  setIsMapAreaSearch(false);
                  setMapAreaResults([]);
                  setLoading(true);
                  const searchResults = await searchRestaurantsByQuery(historyItem);
                  const restaurantsWithDistance = searchResults.map(restaurant => ({
                    ...restaurant,
                    distance: location ? calculateDistance(
                      location.latitude,
                      location.longitude,
                      restaurant.latitude,
                      restaurant.longitude
                    ) : 0
                  }));
                  setRestaurants(restaurantsWithDistance);
                  setLoading(false);
                }}
              >
                <Ionicons name="time-outline" size={16} color={currentColors.gray} style={{ marginRight: 8 }} />
                <Text style={[styles.searchHistoryText, { color: currentColors.text }]}>
                  {historyItem}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}


      </View>

              {/* 지도 섹션 */}
        <Animated.View style={[styles.mapContainer, { height: height - listHeight }]}>
          {location && (
            <MapView
              ref={mapRef}
              style={styles.map}
              provider={PROVIDER_GOOGLE}
              initialRegion={{
                latitude: location.latitude,
                longitude: location.longitude,
                latitudeDelta: 0.01,
                longitudeDelta: 0.01,
              }}
              onRegionChangeComplete={(region) => {
                // 지도 이동 감지
                const bounds = {
                  northeast: {
                    lat: region.latitude + region.latitudeDelta / 2,
                    lng: region.longitude + region.longitudeDelta / 2
                  },
                  southwest: {
                    lat: region.latitude - region.latitudeDelta / 2,
                    lng: region.longitude - region.longitudeDelta / 2
                  }
                };
                setMapBounds(bounds);
                setIsMapMoved(true);
              }}
            >
              {/* 현재 위치 마커 */}
              <Marker
                coordinate={location}
                title="현재 위치"
                pinColor={currentColors.deepBlue}
              />

              {/* 맛집 마커들 */}
              {mapDisplayedRestaurants.map((restaurant) => (
                <Marker
                  key={restaurant.id}
                  coordinate={{
                    latitude: restaurant.latitude,
                    longitude: restaurant.longitude,
                  }}
                  title={restaurant.name}
                  description={restaurant.category}
                  onPress={() => handleMarkerPress(restaurant)}
                />
              ))}
              {/* 디버깅: 현재 페이지 식당 수와 지도 마커 수 확인 */}
              {console.log(`현재 페이지: ${currentPage}, 표시된 식당 수: ${displayedRestaurants.length}, 지도 마커 수: ${mapDisplayedRestaurants.length}`)}
            </MapView>
          )}

          {/* 현재 위치 플로팅 버튼 */}
          <TouchableOpacity
            style={{
              position: 'absolute',
              top: 20,
              right: 20,
              width: 50,
              height: 50,
              borderRadius: 25,
              backgroundColor: currentColors.surface,
              justifyContent: 'center',
              alignItems: 'center',
              elevation: 4,
              shadowColor: currentColors.primary,
              shadowOffset: { width: 0, height: 2 },
              shadowOpacity: 0.2,
              shadowRadius: 4,
              borderWidth: 1,
              borderColor: currentColors.lightGray
            }}
            onPress={getCurrentLocation}
            activeOpacity={0.8}
          >
            <Ionicons name="locate" size={24} color={currentColors.primary} />
          </TouchableOpacity>

          {/* 현재 지도에서 검색 버튼 */}
          {isMapMoved && (
            <TouchableOpacity
              style={{
                position: 'absolute',
                top: 20,
                left: 20,
                backgroundColor: currentColors.primary,
                borderRadius: 20,
                paddingHorizontal: 16,
                paddingVertical: 10,
                elevation: 4,
                shadowColor: currentColors.primary,
                shadowOffset: { width: 0, height: 2 },
                shadowOpacity: 0.3,
                shadowRadius: 4,
              }}
              onPress={async () => {
                if (mapBounds) {
                  setLoading(true);
                  const boundsResults = await searchRestaurantsInBounds(mapBounds);
                  
                  // 거리 계산 추가 (현재 지도 중심점 기준)
                  const mapCenter = {
                    latitude: (mapBounds.northeast.lat + mapBounds.southwest.lat) / 2,
                    longitude: (mapBounds.northeast.lng + mapBounds.southwest.lng) / 2
                  };
                  
                  const restaurantsWithDistance = boundsResults.map(restaurant => ({
                    ...restaurant,
                    distance: calculateDistance(
                      mapCenter.latitude,
                      mapCenter.longitude,
                      restaurant.latitude,
                      restaurant.longitude
                    )
                  }));
                  
                  // 지도 영역 검색 결과를 별도 상태로 저장
                  setMapAreaResults(restaurantsWithDistance);
                  setIsMapAreaSearch(true);
                  setLoading(false);
                  
                  console.log('지도 영역 검색 완료:', boundsResults.length, '개 식당');
                }
              }}
              activeOpacity={0.8}
            >
              <Text style={{ color: '#fff', fontWeight: 'bold', fontSize: 14 }}>
                지도 영역 검색
              </Text>
            </TouchableOpacity>
          )}

        {/* 선택된 맛집 정보 */}
        {selectedRestaurant && (
          <View style={[styles.selectedRestaurantCard, { backgroundColor: currentColors.surface, shadowColor: currentColors.primary }]}>
            <View style={styles.selectedCardHeader}>
              <Text style={[styles.selectedRestaurantName, { color: currentColors.text }]}>
                {selectedRestaurant.name}
              </Text>
              <TouchableOpacity
                onPress={() => setSelectedRestaurant(null)}
                style={styles.closeButton}
              >
                <Ionicons name="close" size={20} color={currentColors.gray} />
              </TouchableOpacity>
            </View>
            <Text style={[styles.selectedRestaurantAddress, { color: currentColors.textSecondary }]}>
              {selectedRestaurant.address}
            </Text>
            <View style={styles.selectedCardDetails}>
              <View style={styles.selectedRatingContainer}>
                <Ionicons name="star" size={16} color={currentColors.yellow} />
                <Text style={[styles.selectedRatingText, { color: currentColors.text }]}>
                  {selectedRestaurant.rating > 0 ? selectedRestaurant.rating.toFixed(1) : '0.0'}
                </Text>
                <Text style={[styles.selectedReviewText, { color: currentColors.textSecondary }]}>
                  ({selectedRestaurant.reviewCount || 0})
                </Text>
              </View>
            </View>
            <TouchableOpacity
              style={[styles.viewDetailButton, { backgroundColor: currentColors.primary }]}
              onPress={() => handleRestaurantPress(selectedRestaurant)}
            >
              <Text style={[styles.viewDetailButtonText, { color: '#fff' }]}>
                상세 정보 보기
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </Animated.View>

      {/* 드래그 가능한 리스트 섹션 */}
      <Animated.View style={[styles.listSection, { height: listHeightAnim, backgroundColor: currentColors.surface, shadowColor: currentColors.primary }]}> 
        {/* 드래그 핸들 */}
        <View {...panResponder.panHandlers} style={[styles.dragHandle, { backgroundColor: currentColors.surface }]}> 
          <View style={[styles.dragIndicator, { backgroundColor: currentColors.border }]} />
        </View>

        {/* 소통탭 스타일의 필터/정렬 바 */}
        <View style={{ backgroundColor: currentColors.surface, paddingHorizontal: 8, paddingTop: 8, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: currentColors.border }}>
          <ScrollView 
            horizontal 
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ alignItems: 'center' }}
          >
            {/* '필터' 버튼 (아이콘 포함) */}
            <TouchableOpacity
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                backgroundColor: activeCategories.length > 0 ? currentColors.primary : currentColors.surface,
                borderRadius: 20,
                paddingVertical: 7,
                paddingHorizontal: 14,
                marginRight: 8,
                elevation: activeCategories.length > 0 ? 2 : 1,
                shadowColor: currentColors.primary,
                shadowOffset: { width: 0, height: 2 },
                shadowOpacity: activeCategories.length > 0 ? 0.2 : 0.1,
                shadowRadius: 4,
                borderWidth: 1,
                borderColor: activeCategories.length > 0 ? currentColors.primary : currentColors.lightGray
              }}
              onPress={() => setCategoryModalVisible(true)}
            >
              <Ionicons name="options-outline" size={16} color={activeCategories.length > 0 ? '#fff' : currentColors.deepBlue} style={{ marginRight: 5, marginTop: 0 }} />
              <Text style={{
                color: activeCategories.length > 0 ? '#FFFFFF' : currentColors.text,
                fontWeight: activeCategories.length > 0 ? 'bold' : '600',
                fontSize: 14
              }}>필터</Text>
            </TouchableOpacity>
            
            {/* 정렬 필터 (소통탭 스타일) */}
            {sortOptions.map(option => (
              <TouchableOpacity
                key={option}
                style={{
                  backgroundColor: activeSort === option ? currentColors.primary : currentColors.surface,
                  borderRadius: 20,
                  paddingVertical: 8,
                  paddingHorizontal: 16,
                  marginRight: 8,
                  elevation: activeSort === option ? 2 : 1,
                  shadowColor: currentColors.primary,
                  shadowOffset: { width: 0, height: 2 },
                  shadowOpacity: activeSort === option ? 0.2 : 0.1,
                  shadowRadius: 4,
                  borderWidth: 1,
                  borderColor: activeSort === option ? currentColors.primary : currentColors.lightGray
                }}
                onPress={() => setActiveSort(option)}
              >
                <Text style={{
                  color: activeSort === option ? '#FFFFFF' : currentColors.text,
                  fontWeight: activeSort === option ? 'bold' : '600',
                  fontSize: 14
                }}>{option}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* 카테고리 선택 모달 */}
        <Modal
          visible={categoryModalVisible}
          transparent
          animationType="fade"
          onRequestClose={() => setCategoryModalVisible(false)}
        >
          <TouchableOpacity
            style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.2)', justifyContent: 'center', alignItems: 'center' }}
            activeOpacity={1}
            onPressOut={() => setCategoryModalVisible(false)}
          >
            <View style={{ backgroundColor: currentColors.surface, borderRadius: 16, padding: 24, minWidth: 220, elevation: 8 }}>
              <Text style={{ fontSize: 18, fontWeight: 'bold', color: currentColors.text, marginBottom: 16, textAlign: 'center' }}>카테고리 선택</Text>
              {categoryOptions.map(option => {
                const selected = activeCategories.includes(option);
                return (
                  <TouchableOpacity
                    key={option}
                    style={{
                      backgroundColor: selected ? currentColors.primary : currentColors.surface,
                      borderRadius: 12,
                      paddingVertical: 12,
                      paddingHorizontal: 16,
                      marginBottom: 8,
                      borderWidth: 1,
                      borderColor: selected ? currentColors.primary : currentColors.lightGray,
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    onPress={() => {
                      if (selected) {
                        setActiveCategories(activeCategories.filter(c => c !== option));
                      } else {
                        setActiveCategories([...activeCategories, option]);
                      }
                    }}
                  >
                    <Text style={{
                      color: selected ? '#FFFFFF' : currentColors.text,
                      fontWeight: selected ? 'bold' : '600',
                      fontSize: 16
                    }}>{option}</Text>
                  </TouchableOpacity>
                );
              })}
              <TouchableOpacity
                style={{ marginTop: 8, alignItems: 'center' }}
                onPress={() => {
                  setActiveCategories([]);
                  setCategoryModalVisible(false);
                }}
              >
                <Text style={{ color: currentColors.gray, fontSize: 14 }}>카테고리 선택 해제</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </Modal>

        {/* 리스트 내용 */}
        <Text style={[styles.resultCount, { color: currentColors.text, backgroundColor: currentColors.background, marginBottom: 8 }]}> 
          {filteredAndSortedRestaurants.length}개의 맛집
        </Text>
                 <ScrollView 
           style={[styles.listContainer, { backgroundColor: currentColors.surface }]} 
           showsVerticalScrollIndicator={false}
           contentContainerStyle={{ paddingBottom: 200 }}
         >
                      {filteredAndSortedRestaurants.map((restaurant) => (
              <View key={restaurant.id}>
                {renderRestaurantCard(restaurant)}
              </View>
            ))}
        </ScrollView>
      </Animated.View>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  searchContainer: {
    padding: 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  searchInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f8f9fa',
    borderRadius: 25,
    paddingHorizontal: 15,
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    height: 40,
    fontSize: 16,
    color: '#1E293B',
  },
  mapContainer: {
    position: 'relative',
  },
  map: {
    flex: 1,
  },
  selectedRestaurantCard: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 4,
    },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 8,
  },
  selectedCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  selectedRestaurantName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1E293B',
    flex: 1,
  },
  closeButton: {
    padding: 4,
  },
  selectedRestaurantAddress: {
    fontSize: 14,
    color: '#666',
    marginBottom: 12,
  },
  selectedCardDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  selectedRatingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  selectedRatingText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1E293B',
    marginLeft: 4,
  },
  selectedReviewText: {
    fontSize: 14,
    color: '#666',
    marginLeft: 4,
  },
  selectedDistanceText: {
    fontSize: 14,
    color: '#035AA6',
    fontWeight: '500',
  },
  selectedTagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  selectedTag: {
    backgroundColor: '#F4D160',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 15,
    marginRight: 8,
    marginBottom: 4,
  },
  selectedTagText: {
    fontSize: 12,
    color: '#1E293B',
    fontWeight: '500',
  },
  viewDetailButton: {
    backgroundColor: '#3B82F6',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    marginTop: 12,
  },
  viewDetailButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  searchHistoryContainer: {
    position: 'absolute',
    top: 72,
    left: 16,
    right: 16,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 12,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    zIndex: 1000,
  },
  searchHistoryTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  searchHistoryItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  searchHistoryText: {
    fontSize: 14,
  },
  listSection: {
    backgroundColor: '#f8f9fa',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: -2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 8,
  },
  dragHandle: {
    alignItems: 'center',
    paddingVertical: 12,
    backgroundColor: '#f8f9fa',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  dragIndicator: {
    width: 40,
    height: 4,
    backgroundColor: '#ddd',
    borderRadius: 2,
  },
  filterContainer: {
    paddingVertical: 10,
    backgroundColor: '#f8f9fa',
  },
  filterButtons: {
    flexDirection: 'row',
    paddingHorizontal: 16,
  },
  filterButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    marginRight: 8,
    borderRadius: 20,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e9ecef',
  },
  filterButtonActive: {
    backgroundColor: '#F4D160',
    borderColor: '#F4D160',
  },
  filterButtonText: {
    fontSize: 14,
    color: '#666',
  },
  filterButtonTextActive: {
    color: '#1E293B',
    fontWeight: '600',
  },
  sortContainer: {
    paddingVertical: 10,
    backgroundColor: '#f8f9fa',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  sortButtons: {
    flexDirection: 'row',
    paddingHorizontal: 16,
  },
  sortButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginRight: 8,
    borderRadius: 15,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e9ecef',
  },
  sortButtonActive: {
    backgroundColor: '#035AA6',
    borderColor: '#035AA6',
  },
  sortButtonText: {
    fontSize: 12,
    color: '#666',
  },
  sortButtonTextActive: {
    color: '#fff',
    fontWeight: '600',
  },
  resultCount: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1E293B',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#f8f9fa',
  },
  listContainer: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  restaurantCard: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    marginHorizontal: 16,
    marginVertical: 6,
    padding: 12,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 3.84,
    elevation: 5,
  },
  cardImage: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: '#f8f9fa',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  cardImageText: {
    fontSize: 24,
  },
  cardContent: {
    flex: 1,
  },
  restaurantName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1E293B',
    marginBottom: 4,
  },
  restaurantCategory: {
    fontSize: 14,
    color: '#666',
    marginBottom: 8,
  },
  cardDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  ratingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  ratingText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1E293B',
    marginLeft: 4,
  },
  reviewText: {
    fontSize: 12,
    color: '#666',
    marginLeft: 4,
  },
  distanceText: {
    fontSize: 12,
    color: '#035AA6',
    fontWeight: '500',
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  tag: {
    backgroundColor: '#F4D160',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 6,
    marginBottom: 4,
  },
  tagText: {
    fontSize: 10,
    color: '#1E293B',
    fontWeight: '500',
  },
  uploadContainer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
});

export default RestaurantMap; 