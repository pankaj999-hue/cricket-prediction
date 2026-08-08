import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './auth';
import Home from './pages/Home';
import Login from './pages/Login';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}