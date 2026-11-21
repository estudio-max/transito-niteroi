import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import '@astryxdesign/core/reset.css';
import '@astryxdesign/core/astryx.css';
import {Theme} from '@astryxdesign/core/theme';
import {tema} from './tema';
import PaginaSinistros from './Sinistros.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Theme theme={tema} mode="dark">
      <PaginaSinistros />
    </Theme>
  </StrictMode>,
);
