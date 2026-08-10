# Inventário R2 do acervo de treino — 2026-08-10

Bucket `epi-monitor-dev` · 7241 frames em `public.training_frames` · tempo total de execução: 79s.

**Nota:** a coleta de frames está ATIVA (câmeras da RVB inserindo linhas em tempo real). Contagens absolutas (total de frames, órfãos) são um snapshot do instante da execução — entre duas execuções em sequência o total do DB variou de 7217→7241 e órfãos de 24→17, ambos consistentes com escrita concorrente, não com um bug do script. Percentuais/agregados (OK vs faltando, quebra por tenant/câmera/dia) são estáveis entre execuções.

## Tabela geral

| Métrica | Contagem | % do total |
|---|---|---|
| Frames no DB | 7241 | 100% |
| Com objeto no R2 (HEAD 200) | 7151 | 98.8% |
| Faltando (HEAD 404) | 90 | 1.2% |
| Acesso negado (HEAD 403) | 0 | 0.0% |
| Outro erro | 0 | 0.0% |

## Quebra por dia

| Data | Frames | OK | Faltando | Outro erro |
|---|---|---|---|---|
| 2026-07-12 | 90 | 0 | 90 | 0 |
| 2026-07-31 | 662 | 662 | 0 | 0 |
| 2026-08-02 | 1 | 1 | 0 | 0 |
| 2026-08-03 | 16 | 16 | 0 | 0 |
| 2026-08-06 | 223 | 223 | 0 | 0 |
| 2026-08-07 | 3696 | 3696 | 0 | 0 |
| 2026-08-08 | 69 | 69 | 0 | 0 |
| 2026-08-09 | 2 | 2 | 0 | 0 |
| 2026-08-10 | 2482 | 2482 | 0 | 0 |

## Quebra por câmera

| Câmera | Frames | OK | Faltando | Outro erro |
|---|---|---|---|---|
| RVB Camera 1 | 1275 | 1275 | 0 | 0 |
| Canal 5 | 1000 | 1000 | 0 | 0 |
| Canal 3 | 978 | 978 | 0 | 0 |
| Canal 4 | 939 | 939 | 0 | 0 |
| Canal 7 | 872 | 872 | 0 | 0 |
| RVB Camera 2 | 768 | 768 | 0 | 0 |
| Canal 6 | 740 | 740 | 0 | 0 |
| Canal 8 | 579 | 579 | 0 | 0 |
| (sem câmera) | 90 | 0 | 90 | 0 |

## Quebra por tenant

| Tenant (slug) | Frames | OK | Faltando | Outro erro |
|---|---|---|---|---|
| rvb | 7151 | 7151 | 0 | 0 |
| e2e-fase-a-validation | 90 | 0 | 90 | 0 |

## Falhas individuais (HEAD != ok)

90 falhas — acima do limite de listagem individual (30). Ver contagens agregadas acima (por dia/câmera/tenant).

## Amostra GET (prova de download real)

30/30 downloads completos bem-sucedidos na amostra aleatória de 30 objetos marcados OK no HEAD.
Tamanho médio dos objetos baixados: 62.8KB.

## GET em toda falha de HEAD (confirma que 404/403 é real, não falso-negativo)

| frame_id | r2_key | GET ok? | detalhe |
|---|---|---|---|
| 16fe388f-f82b-4f0a-abf3-affd388e2d28 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/39ac3fa8-bfc5-4530-90ac-4d418c40b084.jpg` | não | NoSuchKey |
| d135440d-e147-42f3-a5a5-941585a61712 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/a9f5fc50-2617-457d-80f0-b225891e04a8.jpg` | não | NoSuchKey |
| c4cad911-dd2c-4b50-ac6d-e3c86ba3c9a1 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/e666c8c0-793a-42bb-9d0d-f3dcf57e51bd.jpg` | não | NoSuchKey |
| 2781b498-e614-425b-8082-79765b7a6346 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/b5e43dba-ed14-4fa3-9563-dd68f6e08f5e.jpg` | não | NoSuchKey |
| 9cffd8ae-a886-4005-9ee5-7c164f536650 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/31e6f991-7f5d-4fce-a3f8-e0c11aebb744.jpg` | não | NoSuchKey |
| 3b89a8dd-c921-48cd-8129-d40e8a7d51e4 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/42ccf51c-3e1b-44cd-a2c2-17585075a582.jpg` | não | NoSuchKey |
| 02b6b8cd-20fe-46a8-862f-9db4c579deda | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/12843a65-6954-449b-90a7-93ffa6a4fa23.jpg` | não | NoSuchKey |
| 6997caaa-f172-4b06-8278-0e1b33d96ffd | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/eb793ee4-5167-42a4-ab22-6bd047f430f9.jpg` | não | NoSuchKey |
| fa36b2f6-a218-4a65-b362-3c090e1794f4 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/9d1fbeca-3d17-4d01-b547-0e6222f7b017.jpg` | não | NoSuchKey |
| 0d757c6c-a8d9-4bea-b269-33039eccfd5c | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/9d725bb6-43b2-48f6-88ba-813a2c64ec0e.jpg` | não | NoSuchKey |
| 7afeec1c-e665-4aaf-ae64-df789f026ab1 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/62965b8e-31a3-4093-9516-d45f7e450f49.jpg` | não | NoSuchKey |
| b84c8368-eaa6-4feb-85fc-6b5cb5fd1e7e | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/4e300d99-6e51-4ffc-aa55-0124250ce070.jpg` | não | NoSuchKey |
| ae8058f9-6791-4f53-9ac4-30386071e3f0 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/cdbb61f2-c12e-4f75-ace0-2eae9f659af5.jpg` | não | NoSuchKey |
| 2db7276a-c4e5-4e00-b7de-a98ff48fefce | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/dd9a47a0-9117-47a5-8d23-f6a52ebb53ee.jpg` | não | NoSuchKey |
| dc1e53c5-0896-4a9c-8c70-fb6d47964fce | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/bd11e18c-e717-4270-8e58-dc881af4a651.jpg` | não | NoSuchKey |
| 6f8fbda9-d6e8-4085-ae0f-326f43f5d422 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/a74a67f9-fa03-4b71-95bd-8dee3437a54c.jpg` | não | NoSuchKey |
| b9d5e40a-1803-433d-ade5-49814200a9f7 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/414cdf63-d448-4a92-b9cb-b0c13e978b86.jpg` | não | NoSuchKey |
| 6228baff-4e12-4977-8ed9-ed47b5be6047 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/04f48f72-9b69-4ed5-9064-46ac1e8adc32.jpg` | não | NoSuchKey |
| baa5baf8-4236-4935-aaf1-e4207667d799 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/ab9b2699-5c9e-4317-b58e-3fad53cda082.jpg` | não | NoSuchKey |
| 6a17699e-f2a0-48fb-a525-eb54716927d9 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/eac9f86c-4a19-4ac8-90f9-971b5b68f574.jpg` | não | NoSuchKey |
| 99e5d47e-5a55-4ed7-9864-6a053b69cc78 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/b75ec0ff-e287-42a3-add1-3e0021beacda.jpg` | não | NoSuchKey |
| c1fdbc14-273d-4a3b-a1e6-4a0cfdafc437 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/0b17cbfc-5e35-4390-a639-db6fa4bcd700.jpg` | não | NoSuchKey |
| 9e6dfdb7-67ac-4a3f-9f99-299ce3b5806a | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/b440aa52-59e8-4285-837f-b38a2b33a006.jpg` | não | NoSuchKey |
| d56f9213-4158-4814-9435-60d1c2ed0006 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/98c3b5b7-8df8-4219-bffd-87123d036426.jpg` | não | NoSuchKey |
| a01ccd56-423f-4e3e-88bc-4e4d3bd301e6 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/c06cc41b-adc5-43cc-8499-687b81f8928b.jpg` | não | NoSuchKey |
| 896d2397-6de5-4a4a-a8bc-f572c6ae6df7 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/c7ceca8d-22ef-4b19-8553-a7887bb257c4.jpg` | não | NoSuchKey |
| f921835e-da43-4982-abab-8eacd196ab70 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/adea0d71-3f35-4ada-8fcf-ef57cb1b5dca.jpg` | não | NoSuchKey |
| ffcf3be0-df3b-4534-a5b5-7c819c8313b2 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/cf1c4a3d-c9b2-4595-8364-73274610df35.jpg` | não | NoSuchKey |
| f6488396-f686-4320-9522-a282923b1909 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/6cf7b2e2-4079-42dd-b675-86d43bed51f9.jpg` | não | NoSuchKey |
| 82eebc17-56b3-4f57-b82a-942f06aa5d81 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/7337f7da-1104-4ab6-a331-723d6421c5e6.jpg` | não | NoSuchKey |
| 53e1839d-a7c1-40a6-b25d-58bc0813757c | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/d95f6643-7ecc-42db-8e59-08af3125be5b.jpg` | não | NoSuchKey |
| 22a96928-a036-4883-b4ca-47f251fb3141 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/81ccca84-2d0c-4a55-a454-6033eabfd3b9.jpg` | não | NoSuchKey |
| 6154187b-0460-45fd-9645-331a066950b1 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/01028e34-dfed-49fc-9a38-19eeadffb64a.jpg` | não | NoSuchKey |
| 21b61786-1820-4460-87d3-533a6b8ac389 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/fcd5959d-6f54-4926-9483-359067484602.jpg` | não | NoSuchKey |
| b77f549f-4e3e-4068-8448-37b5d3e6a8ea | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/4b5a801b-59be-4099-bf65-c95aedcfc168.jpg` | não | NoSuchKey |
| f8809462-d32e-489c-b3cf-23b61d1c559c | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/58330c59-df1d-40e0-8110-a5040c94532e.jpg` | não | NoSuchKey |
| 3bbbef1e-0730-4bbb-808a-c40c5f9fc029 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/2cb9b0b5-62d8-4b4d-89ee-a941480cc7a2.jpg` | não | NoSuchKey |
| 97a4a2bc-7879-4dcd-9178-375aa7669217 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/0042d18b-bac3-409a-aaaf-98ab16a1d250.jpg` | não | NoSuchKey |
| 5eb03d63-f535-40a4-9287-619e7dea0ef3 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/8a480b6e-f326-4cc4-b73e-e1947af79534.jpg` | não | NoSuchKey |
| 0b81da78-694f-495c-bb73-204c253c96bf | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/4cbc15df-fa49-47d7-8d23-899caa15738d.jpg` | não | NoSuchKey |
| 9758ae1d-9908-4cbc-b45c-d25312556be8 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/965e7b3c-dca9-473f-b837-d8f8aa8e279f.jpg` | não | NoSuchKey |
| 62374fdc-e99d-4dc9-85f9-36d8483bee0f | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/25ab77b3-4cca-4cad-b169-200e3107b62f.jpg` | não | NoSuchKey |
| 134e267d-06bd-4cb9-b66c-2282f58e1523 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/4ef273a0-8506-4955-a559-acc11a67e5cf.jpg` | não | NoSuchKey |
| cd17afb8-fca2-4af5-8dac-f4b30e25e8d9 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/0dc512db-84e8-4fe8-91f4-b88ac16b4897.jpg` | não | NoSuchKey |
| c124b08f-d796-4b14-80b9-99e9725cea8c | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/b88abfb2-173d-412e-8246-b879d3c4e3b2.jpg` | não | NoSuchKey |
| 76b71e96-4b03-4e2f-b3ec-cac83f6819d2 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/f6bcc5fe-65e7-4bb7-8121-905dbfc7af59.jpg` | não | NoSuchKey |
| 69d13a6e-5733-4a74-bc5b-79f41273ab61 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/9a1819a6-2196-4208-830c-e94bf9351819.jpg` | não | NoSuchKey |
| 74e88c20-4a77-4cbe-a392-b9ab9aa7a3ca | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/bb27a54c-4951-4142-a567-f909bf4b820f.jpg` | não | NoSuchKey |
| 02e86e6e-4ae5-4e9c-bb7e-5b2f6c9cf08b | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/97988a19-e577-4ce1-b9de-954b94bf13c4.jpg` | não | NoSuchKey |
| a9d4c1dd-edba-4e9e-81c5-33b3832a0b84 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/420594a5-14bb-4545-889e-7925f6bbe1a6.jpg` | não | NoSuchKey |
| 6a7829f0-ea23-40f9-8c16-ffc3573915d1 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/7b30a5f7-26b3-4b3b-bd9e-f9f15d3ace18.jpg` | não | NoSuchKey |
| 95ea30fe-70cf-4e07-96cd-61ada377bab8 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/aee14329-3df8-42a1-8d88-627c84fa7069.jpg` | não | NoSuchKey |
| ee6fb940-0de4-4a34-8d35-0643042f43c9 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/efd6c6bd-8cb0-416f-9ceb-1e05d43a6f66.jpg` | não | NoSuchKey |
| cf45cc06-d306-4f32-b530-8677cf270e5d | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/9283dd8b-760e-47c9-862a-fdedca715478.jpg` | não | NoSuchKey |
| 505288aa-1d46-4849-9fb3-9b36ced5822b | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/fdfcd4c5-fdef-4473-aa63-1d530ffedb3e.jpg` | não | NoSuchKey |
| d689ccc4-aba8-45b6-8dd5-28b3635db87e | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/4c52a1b4-3f0a-4e64-8e3c-0e1cb3887c3d.jpg` | não | NoSuchKey |
| 7b72a498-ca04-4ae6-890a-f7403ea10181 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/12695ef2-2439-4749-aa3b-091a4b9e1fed.jpg` | não | NoSuchKey |
| 2a18f500-88db-479c-806d-b8fafebfaa9d | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/0cdb1fbe-eef4-4281-b986-fa00a7f584b3.jpg` | não | NoSuchKey |
| 01b28499-093c-4f52-b7d5-54a2709eae59 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/96b3e7f4-b9cd-4c0c-bf90-33a41c66f78f.jpg` | não | NoSuchKey |
| f4842ec3-00a0-495c-9619-12af142f5da8 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/576ad82c-d135-405d-b9ad-08d7ea87081c.jpg` | não | NoSuchKey |
| bf9dbb4c-036d-4372-8696-4237711c9abe | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/b14abc84-54ad-4c50-b71c-d84d541fa7d2.jpg` | não | NoSuchKey |
| 6963bbbd-a593-4599-98f9-0183826fe19d | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/b5ab9049-2d44-4467-b920-274b07e948ed.jpg` | não | NoSuchKey |
| ddc5c5ca-0b14-43e0-9386-4120a793f211 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/3c05c7ec-114e-4694-b8d0-a7d5a57fc769.jpg` | não | NoSuchKey |
| f59bb858-b0fd-46ad-95af-40d1347c6ebb | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/665fbc88-57a0-4b43-aa23-d551d9c16976.jpg` | não | NoSuchKey |
| b1dd95e1-6286-49de-8faa-19f8e8f521c5 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/f5490180-c34a-4c00-a88c-f921e69ff5b5.jpg` | não | NoSuchKey |
| 411c5b83-0e57-476f-9f11-df1145e90d7a | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/5764e8b2-dffb-432c-800e-04083be58baf.jpg` | não | NoSuchKey |
| 556e3338-c2ae-43f6-ab0c-8e4f39611a66 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/b369cc19-7555-4dcb-91b3-2ba982f440c9.jpg` | não | NoSuchKey |
| bac99e82-02c5-45fe-846e-2447eb6e032b | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/2be17881-f08e-493e-8cd6-e6d5b5f9f76a.jpg` | não | NoSuchKey |
| df75ff99-417d-4857-8a8f-0492335bb80e | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/41b0e269-6ff2-4ff6-add6-82b67ca22c35.jpg` | não | NoSuchKey |
| 774f88b3-4fa2-4e69-9cc5-6a77dcd43974 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/c6f9af63-af93-41bb-ab75-0a271867f650.jpg` | não | NoSuchKey |
| 00cdd2fe-885e-469d-9418-ec052cb4e925 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/42c13120-5e64-4ebc-a02e-279d0c8252e3.jpg` | não | NoSuchKey |
| 4507996f-9789-479e-b09d-b5c1cc53d1cc | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/d15485b6-5268-4d03-82fa-087e9ee71436.jpg` | não | NoSuchKey |
| 22a687d5-cc86-4207-8c09-b4c9463d2282 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/0ffa3631-caad-45a8-ba56-da5ee1170656.jpg` | não | NoSuchKey |
| 04e2180d-e553-44c0-8102-42a757929a75 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/14d3a9a0-c4ac-48f0-928e-ce5be3c89497.jpg` | não | NoSuchKey |
| 9b4b73a7-54ff-4fbe-b333-94bbae151e28 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/0129ff91-a582-4caa-bb0a-86949e83a547.jpg` | não | NoSuchKey |
| 7945ff92-ec2a-433c-a124-a13c2711708f | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/908f53d8-9806-4fd2-b731-f4168ca00499.jpg` | não | NoSuchKey |
| dfff87c6-9d94-491d-a421-b651fa8a7148 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/882198ca-47f8-48d4-a08c-0e016149f49c.jpg` | não | NoSuchKey |
| c61846eb-a53d-4905-bd02-13e3ace06d67 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/3d828803-b521-46ae-be7c-a11359a19b59.jpg` | não | NoSuchKey |
| 8e4af5bf-d9e2-4020-ab4b-404618b472d8 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/510ba812-a66a-4e37-8654-215a363aacae.jpg` | não | NoSuchKey |
| 52231650-ca39-4ac4-af3f-a49cef2c84fc | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/788778cc-5df9-4a76-9736-5f816cbc27fe.jpg` | não | NoSuchKey |
| 1783166f-a03d-4d7a-bf9b-324b160e4c43 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/e0b1c003-e60a-4058-bf63-68e47864c400.jpg` | não | NoSuchKey |
| e64f0218-ecc7-4763-87a0-4a07064835e5 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/bab6c2f3-1d3f-4dae-8b08-04bf75529c1c.jpg` | não | NoSuchKey |
| 176a5d46-1ab7-4241-ae8a-b1964894827f | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/c2ccd9e7-3ff8-4046-a704-555146cc1b87.jpg` | não | NoSuchKey |
| cd6aa0f6-e10c-4968-8f8a-2b666fb72b37 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/6ee60ade-6fb5-4430-9e85-18997fde845f.jpg` | não | NoSuchKey |
| fa1e262f-3359-4e01-98cb-7ffc09d1f0b1 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/e4563f15-0491-4163-8411-67fa5d1c72db.jpg` | não | NoSuchKey |
| da56fb4d-cf53-404b-99f6-024c44c2b149 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/973fbb02-a8ce-4ee4-863e-1b811972eb89.jpg` | não | NoSuchKey |
| 346ba230-05e6-4286-9224-fe2c2cbe1e60 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/c1b9cb81-6928-4599-978c-00e4932b5084.jpg` | não | NoSuchKey |
| 1ebacb5f-a99b-429f-ab99-6c260862018c | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/c420dae3-2134-4038-8f11-f4095507bad5.jpg` | não | NoSuchKey |
| a0a4b737-7c2f-4bb4-b5b3-1166bfb061f3 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/a7e7e629-f8bb-475b-96d2-8cb8b42a26fd.jpg` | não | NoSuchKey |
| 0adc30db-bbec-464e-9078-59c45fc5c1e2 | `training-images/a06ec2c9-7cb0-45a4-89f6-8a5dcdb1c4f0/upload/4cca5feb-c810-486b-9bad-37a71bac271e.jpg` | não | NoSuchKey |

## Órfãos (objetos no R2 sob `training-images/` sem linha no DB)

17 objetos no bucket sob `training-images/` não correspondem a nenhum `r2_key` em `public.training_frames` (bucket tem 7168 objetos sob esse prefixo; DB tem 7241 r2_keys).

| Segmento do prefixo (tenant/slug na chave) | Órfãos |
|---|---|
| 63c219d8-fbef-4f3c-a7c9-058c742482e2 | 17 |

## Pesos de modelo no bucket

Varredura do bucket inteiro (7168 objetos) por chaves casando `.pth|.pt|.onnx|.safetensors` ou contendo `sam`/`dino`/`grounding` (case-insensitive).

**Pesos NÃO estão no R2.** Nenhuma chave casou com o padrão de busca.

