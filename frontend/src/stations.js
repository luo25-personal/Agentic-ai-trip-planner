// 可選擇的車站（之後改由 AI Agent 依使用者的需求決定地點）
export const STATIONS = [
  { id: 'aomori', name: '青森', roman: 'Aomori', lat: 40.8286, lng: 140.7337 },
  { id: 'sapporo', name: '札幌', roman: 'Sapporo', lat: 43.0687, lng: 141.3508 },
  { id: 'sendai', name: '仙台', roman: 'Sendai', lat: 38.2601, lng: 140.8822 },
  { id: 'tokyo', name: '東京', roman: 'Tōkyō', lat: 35.6812, lng: 139.7671 },
  { id: 'shinjuku', name: '新宿', roman: 'Shinjuku', lat: 35.6896, lng: 139.7006 },
  { id: 'kanazawa', name: '金沢', roman: 'Kanazawa', lat: 36.5781, lng: 136.6478 },
  { id: 'nagoya', name: '名古屋', roman: 'Nagoya', lat: 35.1709, lng: 136.8815 },
  { id: 'kyoto', name: '京都', roman: 'Kyōto', lat: 34.9858, lng: 135.7588 },
  { id: 'osaka', name: '大阪', roman: 'Ōsaka', lat: 34.7025, lng: 135.4959 },
  { id: 'hakata', name: '博多', roman: 'Hakata', lat: 33.5897, lng: 130.4207 },
]

export const findStation = (id) => STATIONS.find((s) => s.id === id)
