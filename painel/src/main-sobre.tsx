import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import '@astryxdesign/core/reset.css';
import '@astryxdesign/core/astryx.css';
import {Theme} from '@astryxdesign/core/theme';
import {tema} from './tema';
import Sobre from './Sobre.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Theme theme={tema} mode="light">
      <Sobre />
    </Theme>
  </StrictMode>,
);
