const passport = require('passport');
// const Strategy = require('passport-google-oauth').OAuth2Strategy; // Commented out for mocking
// const User = require('./models/User'); // Commented out for mocking

// Mock User object (replace with more specific fields if needed by the frontend/auth HOC)
const MOCK_USER = {
  id: 'mockuserid',
  _id: 'mockuserid', // Often used interchangeably
  googleId: 'mockgoogleid',
  email: 'mock.user@example.com',
  displayName: 'Mock User',
  avatarUrl: '/avatar.png', // Placeholder avatar
  isAdmin: false,
  // Add any other fields expected by withAuth or components (e.g., purchasedBookIds)
  purchasedBookIds: ['mockbook1'],
  isGithubConnected: false,
};

function setupGoogle({ server, ROOT_URL }) {
  // const verify = async (accessToken, refreshToken, profile, verified) => { // Commented out for mocking
  //   let email;
  //   let avatarUrl;
  //
  //   if (profile.emails) {
  //     email = profile.emails[0].value;
  //   }
  //
  //   if (profile.photos && profile.photos.length > 0) {
  //     avatarUrl = profile.photos[0].value.replace('sz=50', 'sz=128');
  //   }
  //
  //   try {
  //     const user = await User.signInOrSignUp({
  //       googleId: profile.id,
  //       email,
  //       googleToken: { accessToken, refreshToken },
  //       displayName: profile.displayName,
  //       avatarUrl,
  //     });
  //     verified(null, user);
  //   } catch (err) {
  //     verified(err);
  //     console.log(err); // eslint-disable-line
  //   }
  // };

  // // Original Strategy setup (Commented out for mocking)
  // passport.use(
  //   new Strategy(
  //     {
  //       clientID: process.env.GOOGLE_CLIENTID,
  //       clientSecret: process.env.GOOGLE_CLIENTSECRET,
  //       callbackURL: `${ROOT_URL}/oauth2callback`,
  //       userProfileURL: 'https://www.googleapis.com/oauth2/v3/userinfo',
  //     },
  //     verify,
  //   ),
  // );

  passport.serializeUser((user, done) => {
    // In mock mode, we might just serialize the mock user's ID
    done(null, user.id);
  });

  passport.deserializeUser((id, done) => {
    // Instead of DB lookup, return the static mock user if the ID matches
    if (id === MOCK_USER.id) {
      done(null, MOCK_USER);
    } else {
      // Handle cases where the ID might not match, e.g., if sessions persist across restarts
      done(new Error('Mock user not found'), null);
    }
    // Original DB lookup (Commented out for mocking)
    // User.findById(id, User.publicFields())
    //   .then(user => {
    //     done(null, user);
    //   })
    //   .catch(error => {
    //     done(error, null);
    //   });
  });

  server.use(passport.initialize());
  server.use(passport.session());

  // Mock /auth/google route
  server.get('/auth/google', (req, res, next) => {
    // 1. Store the intended redirect URL (if provided)
    if (req.query && req.query.redirectUrl && req.query.redirectUrl.startsWith('/')) {
      req.session.finalUrl = req.query.redirectUrl;
    } else {
      req.session.finalUrl = null;
    }

    // 2. "Log in" the mock user using passport
    req.login(MOCK_USER, (err) => {
      if (err) {
        console.error('Mock login failed:', err);
        return next(err);
      }

      // 3. Redirect based on admin status or finalUrl
      if (MOCK_USER.isAdmin) {
        return res.redirect('/admin');
      }
      if (req.session.finalUrl) {
        return res.redirect(`${ROOT_URL}${req.session.finalUrl}`);
      }
      // Default redirect for non-admin user
      return res.redirect('/my-books');
    });

    // Original Google authentication call (Commented out for mocking)
    // const options = {
    //   scope: ['profile', 'email'],
    //   prompt: 'select_account',
    // };
    // passport.authenticate('google', options)(req, res, next);
  });

  // // Original /oauth2callback route (Commented out as it's not needed for mock flow)
  // server.get(
  //   '/oauth2callback',
  //   passport.authenticate('google', {
  //     failureRedirect: '/login',
  //   }),
  //   (req, res) => {
  //     if (req.user && req.user.isAdmin) {
  //       res.redirect('/admin');
  //     } else if (req.user && req.session.finalUrl) {
  //       res.redirect(`${ROOT_URL}${req.session.finalUrl}`);
  //     } else {
  //       res.redirect('/my-books');
  //     }
  //   },
  // );

  // Logout route remains the same
  server.get('/logout', (req, res, next) => {
    req.logout((err) => {
      if (err) {
        next(err);
      }
      res.redirect('/login');
    });
  });
}

module.exports = setupGoogle;

// Check if need googleToken as field for User data model
