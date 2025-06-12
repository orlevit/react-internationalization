import { useTranslation } from 'react-i18next';
import i18n from '../lib/i18n'; // Import i18n instance
import PropTypes from 'prop-types';
import Link from 'next/link';
import Toolbar from '@mui/material/Toolbar';
import Grid from '@mui/material/Grid';
import Hidden from '@mui/material/Hidden';
import Button from '@mui/material/Button';
import Avatar from '@mui/material/Avatar';

import MenuWithAvatar from './MenuWithAvatar';

// Dynamically load available languages from public/locales
const languageOptions = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Español' },
  // Add more languages as needed
];

const optionsMenuCustomer = [
  {
    text: 'My books',
    href: '/customer/my-books',
    as: '/my-books',
  },
  {
    text: 'Log out',
    href: '/logout',
    anchor: true,
  },
];

const optionsMenuAdmin = [
  {
    text: 'Admin',
    href: '/admin',
    as: '/admin',
  },
  {
    text: 'Log out',
    href: '/logout',
    anchor: true,
  },
];

const propTypes = {
  user: PropTypes.shape({
    avatarUrl: PropTypes.string,
    displayName: PropTypes.string,
    isAdmin: PropTypes.bool,
    isGithubConnected: PropTypes.bool,
  }),
  hideHeader: PropTypes.bool,
  redirectUrl: PropTypes.string,
};

const defaultProps = {
  user: null,
  hideHeader: false,
  redirectUrl: '',
};

function Header({ user, hideHeader, redirectUrl }) {
  const { t } = useTranslation();

  // Handle language change
  const handleLanguageChange = (event) => {
    const selectedLanguage = event.target.value;
    i18n.changeLanguage(selectedLanguage); // Change the language dynamically
  };

  return (
    <div
      style={{
        overflow: 'hidden',
        position: 'relative',
        display: 'block',
        top: hideHeader ? '-64px' : '0px',
        transition: 'top 0.5s ease-in',
        backgroundColor: '#24292e',
      }}
    >
      <Toolbar>
        <Grid container direction="row" justifyContent="space-around" alignItems="center">
          <Grid item sm={8} xs={7} style={{ textAlign: 'left' }}>
            {user ? null : (
              <Link href="/">
                <Avatar
                  src="https://storage.googleapis.com/builderbook/logo.svg"
                  alt={t('builder_book_logo_16f388')} // Use translation key
                  style={{ margin: '0px auto 0px 20px', cursor: 'pointer' }}
                />
              </Link>
            )}
          </Grid>
          <Grid item sm={2} xs={2} style={{ textAlign: 'right' }}>
            {user && user.isAdmin && !user.isGithubConnected ? (
              <Hidden mdDown>
                <a href="/auth/github">
                  <Button variant="contained" color="primary">
                    {t('connect_github_77b4b0')} {/* Use translation key */}
                  </Button>
                </a>
              </Hidden>
            ) : null}
          </Grid>
          <Grid item sm={2} xs={3} style={{ textAlign: 'right' }}>
            {user ? (
              <div style={{ whiteSpace: 'nowrap' }}>
                {!user.isAdmin ? (
                  <MenuWithAvatar
                    options={optionsMenuCustomer}
                    src={user.avatarUrl}
                    alt={user.displayName}
                  />
                ) : null}
                {user.isAdmin ? (
                  <MenuWithAvatar
                    options={optionsMenuAdmin}
                    src={user.avatarUrl}
                    alt={user.displayName}
                  />
                ) : null}
              </div>
            ) : (
              <Link
                href={{
                  pathname: '/public/login',
                  query: { redirectUrl },
                }}
                as={{
                  pathname: '/login',
                  query: { redirectUrl },
                }}
                style={{ margin: '0px 20px 0px auto' }}
              >
                Log in
              </Link>
            )}
          </Grid>
          {/* Language Selector */}
          <Grid item sm={2} xs={3} style={{ textAlign: 'right' }}>
            <select
              onChange={handleLanguageChange}
              defaultValue={i18n.language} // Set the current language as default
              style={{
                padding: '5px',
                borderRadius: '4px',
                backgroundColor: '#fff',
                color: '#000',
                border: '1px solid #ccc',
              }}
            >
              {languageOptions.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.label}
                </option>
              ))}
            </select>
          </Grid>
        </Grid>
      </Toolbar>
    </div>
  );
}

Header.propTypes = propTypes;
Header.defaultProps = defaultProps;

export default Header;