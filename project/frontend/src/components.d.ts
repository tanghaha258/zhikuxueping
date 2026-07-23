import type { DefineComponent } from 'vue'

type IconComponent = DefineComponent<object, object, unknown>

declare module 'vue' {
  interface GlobalComponents {
    [key: string]: IconComponent
  }

  interface ComponentCustomProperties {
    User: IconComponent
    UserFilled: IconComponent
    Lock: IconComponent
    View: IconComponent
    Hide: IconComponent
    Plus: IconComponent
    Search: IconComponent
    Refresh: IconComponent
    Bell: IconComponent
    Upload: IconComponent
    List: IconComponent
    MagicStick: IconComponent
    Edit: IconComponent
    Download: IconComponent
    Share: IconComponent
    FolderOpened: IconComponent
    TrendCharts: IconComponent
    FolderAdd: IconComponent
  }
}

export {}
