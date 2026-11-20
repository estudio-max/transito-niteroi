import {HStack} from '@astryxdesign/core/Layout';
import {Link} from '@astryxdesign/core/Link';
import {Text} from '@astryxdesign/core/Text';

const PAGINAS = [
  {id: 'painel', href: '/', nome: 'Painel'},
  {id: 'sobre', href: '/sobre/', nome: 'Sobre o projeto'},
] as const;

// Navegação entre as duas páginas; a atual aparece como texto, não como link.
export function Topo({atual}: {atual: (typeof PAGINAS)[number]['id']}) {
  return (
    <nav aria-label="Páginas do site">
      <HStack gap={6} vAlign="center" wrap="wrap">
        <Text type="body" weight="semibold">
          Fluxo Niterói
        </Text>
        {PAGINAS.map(p =>
          p.id === atual ? (
            <Text key={p.id} type="body" color="secondary" aria-current="page">
              {p.nome}
            </Text>
          ) : (
            <Link key={p.id} href={p.href}>
              {p.nome}
            </Link>
          ),
        )}
      </HStack>
    </nav>
  );
}
