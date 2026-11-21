import {useEffect, useRef, useState} from 'react';
import {useMediaQuery} from '@astryxdesign/core/hooks';

// Ganchos dos elementos "ao vivo" (Vivo.tsx). Quem pede ao sistema para reduzir movimento
// vê tudo parado: os números já no valor final, sem rodas nem varredura girando.

export function useMovimentoReduzido() {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

// Vai do valor anterior ao novo em ~0,9 s quando os dados chegam (a cada minuto). Não
// inventa número entre uma leitura e outra: só anima a troca.
export function useContagem(alvo: number, ms = 900) {
  const reduzir = useMovimentoReduzido();
  const [valor, setValor] = useState(0);
  const atual = useRef(0);
  useEffect(() => {
    if (reduzir) {
      return;
    }
    const de = atual.current;
    const inicio = performance.now();
    let quadro = 0;
    const passo = (t: number) => {
      const k = Math.min(1, (t - inicio) / ms);
      const v = de + (alvo - de) * (1 - Math.pow(1 - k, 3)); // desacelera no fim
      atual.current = v;
      setValor(v);
      if (k < 1) {
        quadro = requestAnimationFrame(passo);
      }
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [alvo, ms, reduzir]);
  return Math.round(reduzir ? alvo : valor);
}
