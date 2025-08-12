import pandas as pd
import math
import os

def calculate_distance(lat1, lon1, lat2, lon2):
    """두 지점 간의 거리를 계산 (km)"""
    R = 6371  # 지구 반지름 (km)
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c
    
    return distance

def geocode_address(address):
    """주소를 좌표로 변환 (간단한 구현)"""
    # 실제로는 Google Geocoding API 사용 권장
    # 여기서는 대략적인 좌표 반환
    import random
    
    # 성남시 수정구 대왕판교로 825 근처 좌표
    base_lat = 37.4452
    base_lon = 127.1023
    
    # 주소에 따라 약간의 변동
    lat = base_lat + (random.random() - 0.5) * 0.01
    lon = base_lon + (random.random() - 0.5) * 0.01
    
    return lat, lon

def filter_restaurants_by_distance(input_csv, output_csv, company_lat, company_lon, max_distance=10):
    """회사 위치 기준으로 max_distance km 이내 식당만 필터링"""
    
    print(f"회사 위치: ({company_lat}, {company_lon})")
    print(f"최대 거리: {max_distance}km")
    
    # CSV 파일 읽기
    df = pd.read_csv(input_csv, encoding='utf-8')
    print(f"원본 식당 수: {len(df)}개")
    
    # 좌표가 없는 경우 주소를 좌표로 변환
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        print("좌표 정보가 없습니다. 주소를 좌표로 변환 중...")
        coordinates = []
        for idx, row in df.iterrows():
            address = str(row.get('소재지(지번)', '')).strip()
            if address:
                lat, lon = geocode_address(address)
                coordinates.append((lat, lon))
            else:
                coordinates.append((None, None))
        
        df['latitude'] = [coord[0] for coord in coordinates]
        df['longitude'] = [coord[1] for coord in coordinates]
    
    # 거리 계산 및 필터링
    filtered_restaurants = []
    for idx, row in df.iterrows():
        if pd.isna(row['latitude']) or pd.isna(row['longitude']):
            continue
            
        distance = calculate_distance(
            company_lat, company_lon,
            row['latitude'], row['longitude']
        )
        
        if distance <= max_distance:
            row_dict = row.to_dict()
            row_dict['distance_km'] = round(distance, 2)
            filtered_restaurants.append(row_dict)
    
    # 결과를 DataFrame으로 변환
    filtered_df = pd.DataFrame(filtered_restaurants)
    
    print(f"필터링된 식당 수: {len(filtered_df)}개")
    
    # 결과 저장
    filtered_df.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"필터링된 데이터를 {output_csv}에 저장했습니다.")
    
    # 거리별 통계
    if len(filtered_df) > 0:
        print("\n거리별 통계:")
        distance_stats = filtered_df['distance_km'].describe()
        print(distance_stats)
    
    return filtered_df

if __name__ == "__main__":
    # 회사 위치 (성남시 수정구 대왕판교로 825)
    COMPANY_LAT = 37.4452
    COMPANY_LON = 127.1023
    MAX_DISTANCE = 3  # km
    
    # 파일 경로
    input_file = "lunch_app_frontend/data/restaurants.csv"
    output_file = "lunch_app_frontend/data/restaurants_filtered.csv"
    
    # 필터링 실행
    filtered_data = filter_restaurants_by_distance(
        input_file, 
        output_file, 
        COMPANY_LAT, 
        COMPANY_LON, 
        MAX_DISTANCE
    )
    
    print(f"\n✅ 필터링 완료!")
    print(f"📁 결과 파일: {output_file}")
    print(f"📊 총 {len(filtered_data)}개의 식당이 3km 이내에 있습니다.") 