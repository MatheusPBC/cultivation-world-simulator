import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { medievalI18n } from './medieval/i18n'
import './medieval/style.css'
createApp(App).use(createPinia()).use(medievalI18n).mount('#app')
