import type { FriendFoe, TargetType } from '../types';
import type { ScenarioTarget, StageScenario } from './types';

const typesByRound: TargetType[] = ['F16', 'Helikopter', 'Mini/Micro İHA', 'Balistik Füze', 'F16', 'Helikopter', 'Mini/Micro İHA', 'Balistik Füze'];

function layeredTarget(round: number, lane: 1 | 2 | 3, start: number, friendFoe: FriendFoe, type: TargetType, suffix: string, hitSecond?: number): ScenarioTarget {
  const yStart = lane === 1 ? 31 : lane === 2 ? 55 : 78;
  const yEnd = lane === 1 ? 18 : lane === 2 ? 65 : 90;
  const enemy = friendFoe === 'Düşman';
  const rangeMid = type === 'F16' ? 12.4 : type === 'Mini/Micro İHA' ? 6.3 : 8.8;
  return {
    id: `S3-R${round}-${suffix}`,
    type,
    friendFoe,
    lane,
    round,
    spawnSecond: start,
    despawnSecond: start + 18,
    width: type === 'F16' ? 13 : 9,
    height: type === 'Mini/Micro İHA' ? 7 : 10,
    candidateFrom: enemy ? start + 5 : undefined,
    candidateUntil: enemy ? hitSecond ?? start + 18 : undefined,
    notes: `Tur ${round}; ${enemy ? 'kırmızı/düşman' : 'camgöbeği/dost'} unsur. Route ve menzil kapısı ayarlanabilir.`,
    route: [
      { second: start, x: 8, y: yStart, range: 16.2, velocity: 1.8, confidence: enemy ? 0.86 : 0.8 },
      { second: start + 7, x: 38, y: yStart + (lane === 1 ? 9 : lane === 2 ? -3 : -8), range: enemy ? rangeMid : rangeMid + 1.5, velocity: 2.1, confidence: enemy ? 0.92 : 0.83 },
      { second: start + 14, x: 67, y: yStart + (lane === 1 ? 5 : lane === 2 ? 2 : -3), range: enemy ? rangeMid - 0.5 : rangeMid + 0.8, velocity: 2.2, confidence: enemy ? 0.94 : 0.82 },
      { second: start + 18, x: 82, y: yEnd, range: 4.6, velocity: 2.3, confidence: enemy ? 0.88 : 0.78 },
    ],
  };
}

const targets: ScenarioTarget[] = [];
for (let round = 1; round <= 8; round += 1) {
  const start = (round - 1) * 20 + (round >= 5 ? 20 : 0);
  const enemyLane = (((round - 1) % 3) + 1) as 1 | 2 | 3;
  const type = typesByRound[round - 1];
  const hitSecondByRound: Record<number, number | undefined> = { 1: 12, 2: 33, 3: 58, 5: 113, 6: 132, 8: 172 };
  targets.push(layeredTarget(round, enemyLane, start, 'Düşman', type, 'X', hitSecondByRound[round]));
  targets.push(layeredTarget(round, ((enemyLane % 3) + 1) as 1 | 2 | 3, start, 'Dost', round % 2 === 0 ? 'F16' : 'Helikopter', 'F1'));
  targets.push(layeredTarget(round, (((enemyLane + 1) % 3) + 1) as 1 | 2 | 3, start, 'Dost', round % 2 === 0 ? 'Helikopter' : 'F16', 'F2'));
}

export const stage3Scenario: StageScenario = {
  id: 'asama-3-otonom-dost-dusman-8-tur',
  stage: 3,
  title: 'Aşama 3 · Dost/Düşman + menzil kapısı provası',
  durationSeconds: 182,
  defaultMode: 'autonomous',
  autoRunning: true,
  sourceRefs: ['docs/sartname_v4.txt:734-736', 'docs/sartname_v4.txt:862-907'],
  assumptions: [
    'Güncel hedef tablosuna göre düşman hedef kırmızı, dost hedef camgöbeği ve bütün hedeflerin altındaki imha balonu kırmızıdır; balon rengi dost/düşman kanıtı değildir.',
    'Her turda bir düşman ve iki dost unsur bulunur; uygun menzil dışı veya dost hedefte strike üretilmez.',
  ],
  routeAdjustableNote: 'Round hedeflerinin route dizileri uçak/İHA rotasını saniye saniye kontrol eder; gerçek parkur ölçüsü gelince sadece bu koordinatlar güncellenir.',
  targets,
  events: [
    { second: 0, kind: 'setup', actor: 'hakem', mode: 'autonomous', autoRunning: true, round: 1, title: 'Aşama 3 başlar', detail: 'Otonom Mod otomatik seçilir; kırmızı düşman, camgöbeği dost ayrımı izlenir.' },
    { second: 1, kind: 'target_launch', actor: 'hedef', round: 1, title: 'Tur 1 kalkış', detail: '1 düşman F16 + 2 dost unsur A→B rotasına girer.' },
    { second: 8, kind: 'track', actor: 'Gökkalkan', targetId: 'S3-R1-X', round: 1, title: 'F16 menzil kapısında', detail: 'Düşman F16 10-15 m aralığında aday seçilir.' },
    { second: 12, kind: 'hit', actor: 'Gökkalkan', targetId: 'S3-R1-X', result: 'hit', points: 30, round: 1, title: 'Tur 1 düşman vuruldu', detail: 'F16 uygun menzilde imha; +30.' },
    { second: 20, kind: 'target_launch', actor: 'hedef', round: 2, title: 'Tur 2 kalkış', detail: 'Düşman Helikopter + 2 dost unsur çıkar.' },
    { second: 30, kind: 'track', actor: 'Gökkalkan', targetId: 'S3-R2-X', round: 2, title: 'Helikopter kilidi', detail: '5-15 m aralığında düşman hedef seçilir.' },
    { second: 33, kind: 'hit', actor: 'Gökkalkan', targetId: 'S3-R2-X', result: 'hit', points: 20, round: 2, title: 'Tur 2 düşman vuruldu', detail: 'Helikopter uygun menzilde imha; +20.' },
    { second: 40, kind: 'target_launch', actor: 'hedef', round: 3, title: 'Tur 3 kalkış', detail: 'Düşman Mini/Micro İHA + 2 dost unsur çıkar.' },
    { second: 55, kind: 'safety', actor: 'güvenlik', targetId: 'S3-R3-F1', result: 'blocked', blockReason: 'BLOCKED_TARGET_GATE', round: 3, title: 'Dost hedef ateş kilidi', detail: 'Dost unsur seçilirse güvenlik kapısı ateşi engeller; strike yok.' },
    { second: 58, kind: 'hit', actor: 'Gökkalkan', targetId: 'S3-R3-X', result: 'hit', points: 10, round: 3, title: 'Tur 3 düşman vuruldu', detail: 'Mini/Micro İHA 0-15 m menzilinde imha; +10.' },
    { second: 60, kind: 'target_launch', actor: 'hedef', round: 4, title: 'Tur 4 kalkış', detail: 'Düşman Balistik Füze + 2 dost unsur çıkar.' },
    { second: 72, kind: 'miss', actor: 'Gökkalkan', targetId: 'S3-R4-X', result: 'miss', points: -10, round: 4, title: 'Tur 4 düşman kaçtı', detail: 'Balistik Füze B çizgisine kadar vurulamaz; -10 ceza.' },
    { second: 80, kind: 'maintenance_request', actor: 'operatör', title: 'Bakım izni talebi', detail: 'Kamera lens temizliği ve LiDAR mock kalibrasyonu için hakemden izin istenir.' },
    { second: 82, kind: 'maintenance_pause', actor: 'hakem', mode: 'maintenance', maintenanceDurationSeconds: 18, title: 'Bakım molası', detail: 'Hakem onayıyla güvenli bakım durumu; atış ve hareket kesilir.' },
    { second: 100, kind: 'maintenance_resume', actor: 'hakem', mode: 'autonomous', autoRunning: true, round: 5, title: 'Bakım biter · Tur 5', detail: 'Otonom takip yeniden başlar.' },
    { second: 101, kind: 'target_launch', actor: 'hedef', round: 5, title: 'Tur 5 kalkış', detail: 'Düşman F16 + 2 dost unsur çıkar.' },
    { second: 113, kind: 'hit', actor: 'Gökkalkan', targetId: 'S3-R5-X', result: 'hit', points: 30, round: 5, title: 'Tur 5 düşman vuruldu', detail: 'F16 10-15 m aralığında vurulur; +30.' },
    { second: 120, kind: 'target_launch', actor: 'hedef', round: 6, title: 'Tur 6 kalkış', detail: 'Düşman Helikopter + 2 dost unsur çıkar.' },
    { second: 132, kind: 'hit', actor: 'Gökkalkan', targetId: 'S3-R6-X', result: 'hit', points: 20, round: 6, title: 'Tur 6 düşman vuruldu', detail: 'Helikopter uygun menzilde imha; +20.' },
    { second: 140, kind: 'target_launch', actor: 'hedef', round: 7, title: 'Tur 7 kalkış', detail: 'Düşman Mini/Micro İHA + 2 dost unsur çıkar.' },
    { second: 156, kind: 'miss', actor: 'Gökkalkan', targetId: 'S3-R7-X', result: 'miss', points: -10, round: 7, title: 'Tur 7 düşman kaçtı', detail: 'Mini/Micro İHA için geç kilit; -10 ceza.' },
    { second: 160, kind: 'target_launch', actor: 'hedef', round: 8, title: 'Tur 8 kalkış', detail: 'Düşman Balistik Füze + 2 dost unsur çıkar.' },
    { second: 172, kind: 'hit', actor: 'Gökkalkan', targetId: 'S3-R8-X', result: 'hit', points: 20, round: 8, title: 'Tur 8 düşman vuruldu', detail: 'Balistik Füze 5-15 m aralığında imha; +20.' },
    { second: 182, kind: 'stage_complete', actor: 'hakem', mode: 'safe', title: 'Aşama 3 tamam', detail: 'Toplam 110 puan; 10 puan barajı geçildi.' },
  ],
};
