import axios from 'axios'

const client = axios.create({
  baseURL: '',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const msg = err?.response?.data?.error || err?.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

export default client
