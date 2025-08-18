import React, { useState, useEffect } from 'react';
import { 
    View, 
    Text, 
    TouchableOpacity, 
    ScrollView, 
    SafeAreaView, 
    ActivityIndicator,
    StyleSheet,
    FlatList 
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';

const BadgeCollection = ({ navigation }) => {
    const [badgesData, setBadgesData] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedBadge, setSelectedBadge] = useState(null);

    useFocusEffect(
        React.useCallback(() => {
            loadBadgesData();
        }, [])
    );

    const loadBadgesData = async () => {
        try {
            setIsLoading(true);
            
            // 배지 정보 로드
            const response = await fetch(`${global.RENDER_SERVER_URL}/api/badges/my-badges/${global.myEmployeeId}`);
            if (response.ok) {
                const data = await response.json();
                setBadgesData(data.badges || []);
            } else {
                // API가 없을 경우 목업 데이터 사용
                setBadgesData(generateMockBadgesData());
            }

        } catch (error) {
            console.error('배지 데이터 로드 실패:', error);
            // 에러 시 목업 데이터 사용
            setBadgesData(generateMockBadgesData());
        } finally {
            setIsLoading(false);
        }
    };

    const generateMockBadgesData = () => {
        const badges = [
            // 첫 방문 배지
            {
                id: 1,
                name: '첫 방문',
                description: '첫 번째 식당을 방문했습니다',
                icon: 'restaurant',
                color: '#10B981',
                is_earned: true,
                earned_date: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
                category: 'first_visit'
            },
            // 리뷰 마스터 배지
            {
                id: 2,
                name: '리뷰 마스터',
                description: '10개의 리뷰를 작성했습니다',
                icon: 'create',
                color: '#3B82F6',
                is_earned: true,
                earned_date: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
                category: 'review'
            },
            // 파티 애호가 배지
            {
                id: 3,
                name: '파티 애호가',
                description: '5개의 파티에 참여했습니다',
                icon: 'people',
                color: '#F59E0B',
                is_earned: true,
                earned_date: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
                category: 'party'
            },
            // 랜덤런치 전문가 배지
            {
                id: 4,
                name: '랜덤런치 전문가',
                description: '20번의 랜덤런치에 참여했습니다',
                icon: 'shuffle',
                color: '#06B6D4',
                is_earned: false,
                category: 'random_lunch',
                progress: 3,
                required: 20
            },
            // 맛집 탐험가 배지
            {
                id: 5,
                name: '맛집 탐험가',
                description: '50개의 다른 식당을 방문했습니다',
                icon: 'map',
                color: '#F59E0B',
                is_earned: false,
                category: 'restaurant',
                progress: 17,
                required: 50
            }
        ];
        return badges;
    };

    const getEarnedBadges = () => {
        return badgesData.filter(badge => badge.is_earned);
    };

    const getUnearnedBadges = () => {
        return badgesData.filter(badge => !badge.is_earned);
    };

    const getProgressPercentage = (badge) => {
        if (badge.is_earned) return 100;
        if (!badge.progress || !badge.required) return 0;
        return Math.min(100, (badge.progress / badge.required) * 100);
    };

    const renderBadgeItem = ({ item }) => (
        <TouchableOpacity 
            style={styles.badgeItem}
            onPress={() => setSelectedBadge(item)}
        >
            <View style={[styles.badgeIcon, { backgroundColor: item.color }]}>
                <Ionicons name={item.icon} size={24} color="#FFFFFF" />
            </View>
            <View style={styles.badgeContent}>
                <Text style={styles.badgeName}>{item.name}</Text>
                <Text style={styles.badgeDescription} numberOfLines={2}>
                    {item.description}
                </Text>
                {!item.is_earned && item.progress !== undefined && (
                    <View style={styles.progressContainer}>
                        <View style={styles.progressBar}>
                            <View 
                                style={[
                                    styles.progressFill, 
                                    { width: `${getProgressPercentage(item)}%` }
                                ]} 
                            />
                        </View>
                        <Text style={styles.progressText}>
                            {item.progress}/{item.required}
                        </Text>
                    </View>
                )}
            </View>
            <View style={styles.badgeStatus}>
                {item.is_earned ? (
                    <Ionicons name="checkmark-circle" size={24} color="#10B981" />
                ) : (
                    <Ionicons name="lock-closed" size={24} color="#CBD5E1" />
                )}
            </View>
        </TouchableOpacity>
    );

    const renderGridBadgeItem = ({ item }) => (
        <TouchableOpacity 
            style={styles.gridBadgeItem}
            onPress={() => setSelectedBadge(item)}
        >
            <View style={[styles.gridBadgeIcon, { backgroundColor: item.color }]}>
                <Ionicons name={item.icon} size={28} color="#FFFFFF" />
            </View>
            <Text style={styles.gridBadgeName} numberOfLines={2}>
                {item.name}
            </Text>
            {item.is_earned ? (
                <View style={styles.gridEarnedIndicator}>
                    <Ionicons name="checkmark-circle" size={16} color="#10B981" />
                </View>
            ) : (
                <View style={styles.gridLockedIndicator}>
                    <Ionicons name="lock-closed" size={16} color="#CBD5E1" />
                </View>
            )}
        </TouchableOpacity>
    );

    if (isLoading) {
        return (
            <SafeAreaView style={styles.container}>
                <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color="#3B82F6" />
                    <Text style={styles.loadingText}>로딩 중...</Text>
                </View>
            </SafeAreaView>
        );
    }

    const earnedBadges = getEarnedBadges();
    const unearnedBadges = getUnearnedBadges();

    return (
        <SafeAreaView style={styles.container}>
            <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
                {/* 헤더 */}
                <View style={styles.header}>
                    <TouchableOpacity 
                        style={styles.backButton}
                        onPress={() => navigation.goBack()}
                    >
                        <Ionicons name="arrow-back" size={24} color="#1E293B" />
                    </TouchableOpacity>
                    <Text style={styles.headerTitle}>배지 컬렉션</Text>
                    <View style={styles.placeholder} />
                </View>

                {/* 요약 카드 */}
                <View style={styles.summaryCard}>
                    <View style={styles.summaryContent}>
                        <Text style={styles.summaryTitle}>배지 현황</Text>
                        <Text style={styles.summaryCount}>
                            {earnedBadges.length}/{badgesData.length}
                        </Text>
                        <Text style={styles.summarySubtitle}>획득한 배지</Text>
                    </View>
                    <View style={styles.summaryIcon}>
                        <Ionicons name="ribbon" size={32} color="#8B5CF6" />
                    </View>
                </View>

                {/* 전체 배지 그리드 */}
                <View style={styles.sectionContainer}>
                    <Text style={styles.sectionTitle}>전체 배지 컬렉션 ({badgesData.length})</Text>
                    <FlatList
                        data={badgesData}
                        renderItem={renderGridBadgeItem}
                        keyExtractor={item => item.id.toString()}
                        numColumns={3}
                        showsVerticalScrollIndicator={false}
                        scrollEnabled={false}
                    />
                </View>

                {/* 획득한 배지 섹션 */}
                <View style={styles.sectionContainer}>
                    <Text style={styles.sectionTitle}>획득한 배지 ({earnedBadges.length})</Text>
                    {earnedBadges.length === 0 ? (
                        <View style={styles.emptyContainer}>
                            <Ionicons name="ribbon-outline" size={48} color="#CBD5E1" />
                            <Text style={styles.emptyText}>아직 획득한 배지가 없습니다</Text>
                        </View>
                    ) : (
                        <FlatList
                            data={earnedBadges}
                            renderItem={renderBadgeItem}
                            keyExtractor={item => item.id.toString()}
                            showsVerticalScrollIndicator={false}
                            scrollEnabled={false}
                        />
                    )}
                </View>

                {/* 미획득 배지 섹션 */}
                <View style={styles.sectionContainer}>
                    <Text style={styles.sectionTitle}>진행 중인 배지 ({unearnedBadges.length})</Text>
                    {unearnedBadges.length === 0 ? (
                        <View style={styles.emptyContainer}>
                            <Ionicons name="trophy-outline" size={48} color="#CBD5E1" />
                            <Text style={styles.emptyText}>모든 배지를 획득했습니다!</Text>
                        </View>
                    ) : (
                        <FlatList
                            data={unearnedBadges}
                            renderItem={renderBadgeItem}
                            keyExtractor={item => item.id.toString()}
                            showsVerticalScrollIndicator={false}
                            scrollEnabled={false}
                        />
                    )}
                </View>
            </ScrollView>

            {/* 배지 상세 모달 */}
            {selectedBadge && (
                <View style={styles.modalOverlay}>
                    <View style={styles.modalContent}>
                        <View style={styles.modalHeader}>
                            <Text style={styles.modalTitle}>배지 상세 정보</Text>
                            <TouchableOpacity onPress={() => setSelectedBadge(null)}>
                                <Ionicons name="close" size={24} color="#64748B" />
                            </TouchableOpacity>
                        </View>
                        <View style={styles.modalBody}>
                            <View style={[styles.modalBadgeIcon, { backgroundColor: selectedBadge.color }]}>
                                <Ionicons name={selectedBadge.icon} size={32} color="#FFFFFF" />
                            </View>
                            <Text style={styles.modalBadgeName}>{selectedBadge.name}</Text>
                            <Text style={styles.modalBadgeDescription}>{selectedBadge.description}</Text>
                            {selectedBadge.is_earned && selectedBadge.earned_date && (
                                <Text style={styles.modalEarnedDate}>
                                    획득일: {new Date(selectedBadge.earned_date).toLocaleDateString('ko-KR')}
                                </Text>
                            )}
                            {!selectedBadge.is_earned && selectedBadge.progress !== undefined && (
                                <View style={styles.modalProgress}>
                                    <Text style={styles.modalProgressText}>
                                        진행률: {selectedBadge.progress}/{selectedBadge.required}
                                    </Text>
                                    <View style={styles.modalProgressBar}>
                                        <View 
                                            style={[
                                                styles.modalProgressFill, 
                                                { width: `${getProgressPercentage(selectedBadge)}%` }
                                            ]} 
                                        />
                                    </View>
                                </View>
                            )}
                        </View>
                    </View>
                </View>
            )}
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#F8FAFC',
    },
    scrollView: {
        flex: 1,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    loadingText: {
        marginTop: 16,
        fontSize: 16,
        color: '#64748B',
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 20,
        paddingVertical: 16,
        backgroundColor: '#FFFFFF',
        borderBottomWidth: 1,
        borderBottomColor: '#E2E8F0',
    },
    backButton: {
        padding: 4,
    },
    headerTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#1E293B',
    },
    placeholder: {
        width: 32,
    },
    summaryCard: {
        margin: 20,
        padding: 20,
        backgroundColor: '#FFFFFF',
        borderRadius: 16,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 8,
        elevation: 4,
        flexDirection: 'row',
        alignItems: 'center',
    },
    summaryContent: {
        flex: 1,
    },
    summaryTitle: {
        fontSize: 16,
        color: '#64748B',
        marginBottom: 4,
    },
    summaryCount: {
        fontSize: 28,
        fontWeight: 'bold',
        color: '#8B5CF6',
        marginBottom: 4,
    },
    summarySubtitle: {
        fontSize: 14,
        color: '#64748B',
    },
    summaryIcon: {
        marginLeft: 16,
    },
    sectionContainer: {
        paddingHorizontal: 20,
        marginBottom: 20,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#1E293B',
        marginBottom: 16,
    },
    // 그리드 레이아웃 스타일
    gridRow: {
        justifyContent: 'space-between',
        marginBottom: 16,
    },
    gridBadgeItem: {
        width: '30%',
        alignItems: 'center',
        backgroundColor: '#FFFFFF',
        padding: 12,
        borderRadius: 12,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.05,
        shadowRadius: 4,
        elevation: 2,
        position: 'relative',
        marginBottom: 16,
        marginHorizontal: '1.66%',
    },
    gridBadgeIcon: {
        width: 56,
        height: 56,
        borderRadius: 28,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 8,
    },
    gridBadgeName: {
        fontSize: 12,
        fontWeight: '600',
        color: '#1E293B',
        textAlign: 'center',
        lineHeight: 16,
        height: 32,
    },
    gridEarnedIndicator: {
        position: 'absolute',
        top: 8,
        right: 8,
    },
    gridLockedIndicator: {
        position: 'absolute',
        top: 8,
        right: 8,
    },
    // 기존 리스트 레이아웃 스타일
    badgeItem: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#FFFFFF',
        padding: 16,
        borderRadius: 12,
        marginBottom: 12,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.05,
        shadowRadius: 4,
        elevation: 2,
    },
    badgeIcon: {
        width: 48,
        height: 48,
        borderRadius: 24,
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: 12,
    },
    badgeContent: {
        flex: 1,
    },
    badgeName: {
        fontSize: 16,
        fontWeight: '600',
        color: '#1E293B',
        marginBottom: 4,
    },
    badgeDescription: {
        fontSize: 14,
        color: '#64748B',
        marginBottom: 8,
    },
    progressContainer: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    progressBar: {
        flex: 1,
        height: 6,
        backgroundColor: '#E2E8F0',
        borderRadius: 3,
        marginRight: 8,
        overflow: 'hidden',
    },
    progressFill: {
        height: '100%',
        backgroundColor: '#3B82F6',
        borderRadius: 3,
    },
    progressText: {
        fontSize: 12,
        color: '#64748B',
        minWidth: 30,
    },
    badgeStatus: {
        marginLeft: 8,
    },
    emptyContainer: {
        alignItems: 'center',
        paddingVertical: 40,
    },
    emptyText: {
        fontSize: 16,
        color: '#64748B',
        marginTop: 12,
    },
    modalOverlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 20,
    },
    modalContent: {
        backgroundColor: '#FFFFFF',
        borderRadius: 16,
        padding: 20,
        width: '100%',
        maxWidth: 400,
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 20,
    },
    modalTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#1E293B',
    },
    modalBody: {
        alignItems: 'center',
    },
    modalBadgeIcon: {
        width: 64,
        height: 64,
        borderRadius: 32,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 16,
    },
    modalBadgeName: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#1E293B',
        marginBottom: 8,
        textAlign: 'center',
    },
    modalBadgeDescription: {
        fontSize: 14,
        color: '#64748B',
        textAlign: 'center',
        marginBottom: 16,
        lineHeight: 20,
    },
    modalEarnedDate: {
        fontSize: 12,
        color: '#10B981',
        fontWeight: '500',
    },
    modalProgress: {
        width: '100%',
        alignItems: 'center',
    },
    modalProgressText: {
        fontSize: 14,
        color: '#64748B',
        marginBottom: 8,
    },
    modalProgressBar: {
        width: '100%',
        height: 8,
        backgroundColor: '#E2E8F0',
        borderRadius: 4,
        overflow: 'hidden',
    },
    modalProgressFill: {
        height: '100%',
        backgroundColor: '#3B82F6',
        borderRadius: 4,
    },
});

export default BadgeCollection; 
