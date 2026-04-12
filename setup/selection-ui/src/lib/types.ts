export interface SceneItem {
  asset_id: string;
  type: 'IMAGE' | 'VIDEO';
  selected: boolean;
  favorite: boolean;
  duration?: number;
}
