export interface DataSource {
  id: number;
  name: string;
  url: string;
  active: string; // "true" or "false"
}

export type CreateDataSource = Omit<DataSource, 'id'>;
export type UpdateDataSource = Partial<CreateDataSource>;
