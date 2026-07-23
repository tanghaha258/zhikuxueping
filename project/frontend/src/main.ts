import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { registerSessionExpiredHandler } from '@/shared/auth/session'
import { useUserStore } from '@/stores/user'

// 全局样式
import './styles/global.scss'

const app = createApp(App)

// 注册 Pinia
const pinia = createPinia()
app.use(pinia)

const userStore = useUserStore(pinia)
registerSessionExpiredHandler(() => {
  userStore.clearSession()
  if (router.currentRoute.value.path !== '/login') {
    void router.replace('/login')
  }
})

// 注册 Vue Router
app.use(router)

// 注册 Element Plus
app.use(ElementPlus, { locale: undefined })

// 全局注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 挂载应用
app.mount('#app')
