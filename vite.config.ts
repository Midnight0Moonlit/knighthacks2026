import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', //Exposes Server to the Local Network
    port: 5173,

    //NOTE: THIS MEANS THE LAPTOP RUNNING THE SERVER AND THE IPAD MUST BE CONNECTED ONTO A HOTSPOT
    //This is dangerous because it exposes the server to the local network, but it is necessary for testing on an iPad.
  }
})
