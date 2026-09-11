import axios from 'axios'

const client = axios.create({
  baseURL: '',
  timeout: 600000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') {
      return Promise.reject(err)
    }
    const body = err?.response?.data
    const nested = body?.error && typeof body.error === 'object' ? body.error.message : body?.error
    const msg = body?.message || nested || err?.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

export default client
