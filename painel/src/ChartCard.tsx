import type {ReactNode} from 'react';
import {VStack, HStack} from '@astryxdesign/core/Layout';
import {Text, Heading} from '@astryxdesign/core/Text';
import {Card} from '@astryxdesign/core/Card';
import {Collapsible} from '@astryxdesign/core/Collapsible';
import {Icon} from '@astryxdesign/core/Icon';
import {InformationCircleIcon} from '@heroicons/react/24/outline';

// "Entenda este gráfico": uma leitura do fenômeno em palavras, fechada até a pessoa abrir.
// Bloco recolhível (Collapsible) e não popover: em navegador de celular sem o popover nativo,
// o conteúdo aparecia aberto no meio da página.
export interface Leitura {
  texto: string[];
  comoLer: string;
}

function LeituraEmPalavras({leitura}: {leitura: Leitura}) {
  return (
    <VStack gap={2}>
      {leitura.texto.map(f => (
        <Text key={f} type="body">
          {f}
        </Text>
      ))}
      {leitura.comoLer && (
        <Text type="supporting" color="secondary">
          {`Como ler: ${leitura.comoLer}`}
        </Text>
      )}
    </VStack>
  );
}

export function ChartCard({
  titulo,
  apoio,
  children,
  leitura,
}: {
  titulo: string;
  apoio: string;
  children: ReactNode;
  leitura?: Leitura;
}) {
  return (
    <Card>
      <VStack gap={4}>
        <VStack gap={1}>
          <Heading level={4} accessibilityLevel={3}>
            {titulo}
          </Heading>
          <Text type="body" color="secondary">
            {apoio}
          </Text>
          {leitura && (
            <Collapsible
              defaultIsOpen={false}
              trigger={
                <HStack gap={1} vAlign="center">
                  <Icon icon={InformationCircleIcon} size="sm" />
                  <Text type="body" weight="semibold">
                    Entenda este gráfico
                  </Text>
                </HStack>
              }>
              <LeituraEmPalavras leitura={leitura} />
            </Collapsible>
          )}
        </VStack>
        {children}
      </VStack>
    </Card>
  );
}

