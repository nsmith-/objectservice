import React from 'react';
import { AuthProvider } from 'react-oidc-context';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/App.css';

const oidcConfig = {
    client_id: process.env.REACT_APP_OAUTH_CLIENT_ID,
    redirect_uri: `${process.env.REACT_APP_OAUTH_REDIRECT_URI_BASE}/authentication/callback`,
    response_type: 'code',
    scope: 'openid profile email',
    authority: process.env.REACT_APP_OIDC_PROVIDER,
    silent_redirect_uri: `${process.env.REACT_APP_OAUTH_REDIRECT_URI_BASE}/authentication/silent_callback`,
    automaticSilentRenew: true,
    loadUserInfo: true,
    onSigninCallback: () => {
        // Redirect to the normal URL after authentication
        window.history.replaceState({}, document.title, window.location.pathname);
    },
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
    <React.StrictMode>
        <AuthProvider {...oidcConfig}>
            <App />
        </AuthProvider>
    </React.StrictMode>
);