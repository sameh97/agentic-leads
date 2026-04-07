export interface Lead {
  name:           string
  primary_email:  string
  email_verified: boolean
  email_catchall: boolean
  email_status:   string
  owner_name:     string
  owner_position: string
  phone:          string
  website:        string
  address:        string
  rating:         number
  review_count:   number
  score:          number
  category:       string
  source:         string
}