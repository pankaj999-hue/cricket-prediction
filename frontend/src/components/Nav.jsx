import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

const STATUS_TEXT = {
  connecting: 'CONNECTING…',
  online: 'ENGINE CONNECTED',
  offline: 'ENGINE OFFLINE',
};

export default function Nav({ status }) {
  const { user, getToken, clearSession } = useAuth();
  const navigate = useNavigate();

  async function handleLogout(e) {
    e.preventDefault();
    try {
      const headers = { 'Content-Type': 'application/json' };
      const token = getToken();
      if (token) headers['Authorization'] = 'Bearer ' + token;
      await fetch('/api/auth/logout', {
        method: 'POST', headers, credentials: 'same-origin', body: '{}',
      });
    } catch {}
    clearSession();
    navigate('/login');
  }

  return (
    <nav>
      <div className="logo"><span className="logo-chev" />ANTARYAMI</div>
      <div className="nav-right">
        <div className={'nav-status' + (status === 'offline' ? ' offline' : '')}>
          <span className="pulse" />
          <span>{STATUS_TEXT[status] || STATUS_TEXT.connecting}</span>
        </div>
        {user && user.email ? (
          <>
            {user.is_admin && (
              <a className="nav-admin" href="#/admin" onClick={(e) => { e.preventDefault(); navigate('/admin'); }}>Admin</a>
            )}
            <a className="nav-auth out" href="#" onClick={handleLogout}>Sign out · {user.email}</a>
          </>
        ) : (
          <a className="nav-auth" href="/login" onClick={(e) => { e.preventDefault(); navigate('/login'); }}>Sign in</a>
        )}
      </div>
    </nav>
  );
}